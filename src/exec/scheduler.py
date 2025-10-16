from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

import yaml
import pyautogui as pg

from src.exec.runner import ActionRunner
from src.ocr.extract import scan_once
from src.storage.db import ensure_db, insert_action, insert_snapshot, new_run, end_run, upsert_item


class JobScheduler:
    """
    Lê um arquivo YAML de jobs e os executa em sequência.
    Suporta:
      - collect_watchlist: usa ActionRunner + scan_once (BUY/SELL)
      - collect_category: chama uma ação de navegação definida no actions.yaml
                         e percorre a lista com setas, cadastrando itens (tabela items).
    """
    def __init__(self, cfg_ui: str, cfg_actions: str, cfg_ocr: str, jobs_file: str):
        self.cfg_ui = cfg_ui
        self.cfg_actions = cfg_actions
        self.cfg_ocr = cfg_ocr
        self.jobs_file = Path(jobs_file)

    def _load_jobs(self) -> List[Dict[str, Any]]:
        with self.jobs_file.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data.get("jobs", [])

    # ---------- Jobs ----------
    def _job_collect_watchlist(self, run_id: int, job: Dict[str, Any]):
        views = [v.strip().upper() for v in job.get("views", ["BUY_LIST"])]
        items = job.get("items", [])  # pode vir de arquivo ou inline
        watchlist_csv = job.get("watchlist_csv")
        if watchlist_csv and not items:
            # CSV simples com "item_name"
            lines = [l.strip() for l in Path(watchlist_csv).read_text(encoding="utf-8").splitlines() if l.strip()]
            header = (lines[0].lower() if lines else "")
            items = [l for l in (lines[1:] if "item_name" in header else lines)]

        ar = ActionRunner(self.cfg_ui, self.cfg_actions, self.cfg_ocr)
        for item in items:
            insert_action(self.con, run_id, "open_item:start", {"item": item})
            ok = ar.run("open_item", {"item_name": item})
            insert_action(self.con, run_id, "open_item:end", {"item": item, "ok": ok})
            if not ok:
                continue

            for v in views:
                step_action = "open_buy_orders" if v == "BUY_LIST" else "open_sell_orders"
                insert_action(self.con, run_id, f"{step_action}:start", {"item": item})
                ok2 = ar.run(step_action, {"item_name": item})
                insert_action(self.con, run_id, f"{step_action}:end", {"item": item, "ok": ok2})
                if not ok2:
                    continue

                rows = scan_once(v, self.cfg_ocr, self.cfg_ui, page_index=0, scroll_pos=0.0)
                for r in rows:
                    insert_snapshot(self.con, run_id, r)
                insert_action(self.con, run_id, "scan_page", {"item": item, "view": v, "rows": len(rows)})

                # opcional: cadastrar item no catálogo, sem categoria conhecida
                upsert_item(self.con, name=item, category=None, subcategory=None, tags_json=None, source="watchlist")

    def _job_collect_category(self, run_id: int, job: Dict[str, Any]):
        """
        Requer no actions.yaml uma ação de navegação (ex.: open_category_Ores).
        Depois varre a lista com 'down', lendo o primeiro nome e cadastrando.
        Parâmetros:
          - action_name: str (obrigatório)
          - category: str
          - subcategory: str | None
          - limit_items: int (padrão 100)
          - views: ["BUY_LIST","SELL_LIST"]
        """
        action_name = job.get("action_name")
        if not action_name:
            insert_action(self.con, run_id, "collect_category:error", {"reason": "action_name ausente"})
            return

        category = job.get("category")
        subcategory = job.get("subcategory")
        limit_items = int(job.get("limit_items", 100))
        views = [v.strip().upper() for v in job.get("views", ["BUY_LIST"])]

        ar = ActionRunner(self.cfg_ui, self.cfg_actions, self.cfg_ocr)
        insert_action(self.con, run_id, "open_category:start", {"action": action_name, "category": category, "subcategory": subcategory})
        ok = ar.run(action_name, {"category": category, "subcategory": subcategory})
        insert_action(self.con, run_id, "open_category:end", {"ok": ok})
        if not ok:
            return

        seen = set()
        for _ in range(limit_items):
            name = ar.read_first_row_name()
            if not name or name in seen:
                # heurística simples: repetiu -> fim
                break
            seen.add(name)

            # cadastra no catálogo com a categoria informada
            upsert_item(self.con, name=name, category=category, subcategory=subcategory, tags_json=None, source="ocr")

            # coleta BUY/SELL conforme solicitado
            for v in views:
                step_action = "open_buy_orders" if v == "BUY_LIST" else "open_sell_orders"
                ar.run(step_action, {"item_name": name})
                rows = scan_once(v, self.cfg_ocr, self.cfg_ui, page_index=0, scroll_pos=0.0)
                for r in rows:
                    # sobrescrever o item_name lido para garantir consistência
                    r["item_name"] = name
                    insert_snapshot(self.con, run_id, r)
                insert_action(self.con, run_id, "scan_page", {"item": name, "view": v, "rows": len(rows)})

            # vai para o próximo item visual com tecla ↓ (supondo foco na lista)
            pg.press("down")
            time.sleep(0.15)

    # ---------- Execução ----------
    def run_once(self):
        self.con = ensure_db()
        run_id = new_run(self.con, mode="jobs", notes=self.jobs_file.name)
        try:
            jobs = self._load_jobs()
            for j in jobs:
                kind = (j.get("kind") or "").lower()
                if kind == "collect_watchlist":
                    self._job_collect_watchlist(run_id, j)
                elif kind == "collect_category":
                    self._job_collect_category(run_id, j)
                else:
                    insert_action(self.con, run_id, "job:skip", {"unknown_kind": j.get("kind")})
        finally:
            end_run(self.con, run_id)

    def watch_forever(self, interval_s: float = 1.0):
        """Reexecuta sempre que o arquivo mudar (timestamp)."""
        last_mtime = 0.0
        while True:
            try:
                m = self.jobs_file.stat().st_mtime
                if m != last_mtime:
                    last_mtime = m
                    self.run_once()
            except FileNotFoundError:
                pass
            time.sleep(interval_s)
