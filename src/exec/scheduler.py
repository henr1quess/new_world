from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml
import pyautogui as pg

from src.exec.runner import ActionRunner
from src.exec.watchdog import assert_window_alive
from src.ocr.extract import scan_once
from src.storage.db import (
    ensure_db,
    insert_action,
    insert_my_order_snapshot,
    insert_snapshot,
    mark_order_seen_now,
    new_run,
    set_order_closed,
    update_order_fill,
    end_run,
    upsert_item,
)


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
        assert_window_alive()
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
        assert_window_alive()
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

    def _job_reconcile_orders(self, run_id: int, job: Dict[str, Any]):
        assert_window_alive()

        price_epsilon_val = job.get("price_match_epsilon", 0.005)
        if price_epsilon_val is None:
            price_epsilon_val = 0.005
        price_epsilon = float(price_epsilon_val)
        snapshot_window_val = job.get("snapshot_window_minutes", 120)
        if snapshot_window_val is None:
            snapshot_window_val = 120
        snapshot_window_minutes = int(snapshot_window_val)
        close_missing_after_minutes = job.get("close_missing_after_minutes")
        missing_close_status = job.get("missing_close_status")
        run_ui = bool(job.get("open_ui", True))
        side = job.get("side")

        insert_action(
            self.con,
            run_id,
            "reconcile_orders:start",
            {
                "price_eps": price_epsilon,
                "window_minutes": snapshot_window_minutes,
                "close_missing_after": close_missing_after_minutes,
            },
        )

        if run_ui:
            ar = ActionRunner(self.cfg_ui, self.cfg_actions, self.cfg_ocr)
            action_payload = {"side": side} if side else {}
            insert_action(
                self.con,
                run_id,
                "open_my_orders:start",
                {"payload": action_payload},
            )
            ok = ar.run("open_my_orders", action_payload)
            insert_action(
                self.con,
                run_id,
                "open_my_orders:end",
                {"payload": action_payload, "ok": ok},
                success=1 if ok else 0,
            )
            if not ok:
                insert_action(
                    self.con,
                    run_id,
                    "reconcile_orders:abort",
                    {"reason": "open_my_orders_failed"},
                    success=0,
                )
                return
        else:
            insert_action(
                self.con,
                run_id,
                "open_my_orders:skip",
                {"reason": "open_ui_disabled"},
            )

        imported_rows = 0
        for row in job.get("snapshots", []) or []:
            if not isinstance(row, dict):
                continue
            required_keys = {"item_name", "side", "price"}
            if not required_keys.issubset(row):
                continue
            insert_my_order_snapshot(self.con, row)
            imported_rows += 1
        if imported_rows:
            insert_action(
                self.con,
                run_id,
                "reconcile_orders:snapshots_imported",
                {"rows": imported_rows},
            )

        params: List[Any] = []
        query = """
            SELECT id, ts, item_name, side, price, qty_remaining, settlement
            FROM my_orders_snapshots
        """
        if snapshot_window_minutes > 0:
            query += " WHERE datetime(ts) >= datetime('now', ?)"
            params.append(f"-{snapshot_window_minutes} minutes")
        query += " ORDER BY datetime(ts) DESC"

        cur = self.con.execute(query, params)
        snapshot_rows = [dict(row) for row in cur.fetchall()]

        def _normalize_item(name: str | None) -> str:
            return (name or "").strip().casefold()

        def _parse_float(val: Any) -> float | None:
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                txt = val.strip().replace(" ", "")
                for candidate in (txt.replace(",", "."), txt.replace(".", "").replace(",", ".")):
                    try:
                        return float(candidate)
                    except ValueError:
                        continue
            return None

        def _parse_int(val: Any) -> int | None:
            if val is None:
                return None
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)
            if isinstance(val, str):
                digits = "".join(ch for ch in val if ch.isdigit() or ch == "-")
                if not digits or digits == "-":
                    return None
                try:
                    return int(digits)
                except ValueError:
                    return None
            return None

        def _parse_dt(val: Any) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            txt = str(val)
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(txt, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(txt)
            except ValueError:
                return None

        grouped: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for snap in snapshot_rows:
            price_val = _parse_float(snap.get("price"))
            if price_val is None:
                continue
            side_val = (snap.get("side") or "").upper()
            item_key = _normalize_item(snap.get("item_name"))
            snap["price"] = price_val
            snap["qty_remaining"] = _parse_int(snap.get("qty_remaining"))
            snap["_ts_obj"] = _parse_dt(snap.get("ts"))
            grouped[(item_key, side_val)].append(snap)

        for entries in grouped.values():
            entries.sort(key=lambda s: s.get("_ts_obj") or datetime.min, reverse=True)

        cur = self.con.execute(
            """
            SELECT my_order_id, item_name, side, price, qty_requested, qty_filled,
                   status, last_seen_at
            FROM my_orders
            WHERE status IN ('PENDING','ACTIVE','PARTIAL')
            """
        )
        active_orders = [dict(row) for row in cur.fetchall()]

        now = datetime.utcnow()
        matched = 0
        filled = 0
        closed_missing = 0

        for order in active_orders:
            item_key = _normalize_item(order.get("item_name"))
            side_val = (order.get("side") or "").upper()
            order_price = _parse_float(order.get("price"))
            if order_price is None:
                continue
            order_qty_req = _parse_int(order.get("qty_requested")) or 0
            order_qty_filled = _parse_int(order.get("qty_filled")) or 0

            candidates = grouped.get((item_key, side_val), [])
            match = None
            for snap in candidates:
                snap_price = snap["price"]
                if abs(snap_price - order_price) <= price_epsilon:
                    match = snap
                    break

            if match:
                matched += 1
                mark_order_seen_now(self.con, order["my_order_id"])

                qty_remaining = match.get("qty_remaining")
                fill_delta = 0
                total_filled = order_qty_filled
                if qty_remaining is not None:
                    qty_remaining = max(qty_remaining, 0)
                    total_filled = max(0, min(order_qty_req, order_qty_req - qty_remaining))
                    fill_delta = total_filled - order_qty_filled
                    if fill_delta > 0:
                        update_order_fill(self.con, order["my_order_id"], fill_delta)
                order_qty_filled = total_filled
                closed_now = False
                if order_qty_req > 0 and order_qty_filled >= order_qty_req:
                    set_order_closed(self.con, order["my_order_id"], "FILLED")
                    filled += 1
                    closed_now = True
                insert_action(
                    self.con,
                    run_id,
                    "reconcile_orders:match",
                    {
                        "my_order_id": order["my_order_id"],
                        "qty_delta": fill_delta,
                        "snapshot_id": match.get("id"),
                        "qty_remaining": qty_remaining,
                        "closed": closed_now,
                    },
                )
                continue

            insert_action(
                self.con,
                run_id,
                "reconcile_orders:missing",
                {"my_order_id": order["my_order_id"], "status": order.get("status")},
                success=0,
            )

            if close_missing_after_minutes is None:
                continue

            last_seen_dt = _parse_dt(order.get("last_seen_at"))
            if last_seen_dt is None:
                continue

            if now - last_seen_dt < timedelta(minutes=float(close_missing_after_minutes)):
                continue

            final_status = missing_close_status
            if final_status is None and (order_qty_filled >= order_qty_req > 0):
                final_status = "FILLED"
            if final_status:
                set_order_closed(
                    self.con,
                    order["my_order_id"],
                    str(final_status),
                    {
                        "reason": "not_seen_recently",
                        "last_seen_at": order.get("last_seen_at"),
                    },
                )
                closed_missing += 1

        insert_action(
            self.con,
            run_id,
            "reconcile_orders:summary",
            {"matched": matched, "filled": filled, "closed_missing": closed_missing},
        )

    # ---------- Execução ----------
    def run_once(self):
        # Garanta que a janela está ativa antes de abrir o banco ou registrar runs.
        assert_window_alive()

        self.con = ensure_db()
        self.con.row_factory = sqlite3.Row
        run_id = new_run(self.con, mode="jobs", notes=self.jobs_file.name)
        try:
            jobs = self._load_jobs()
            for j in jobs:
                kind = (j.get("kind") or "").lower()
                if kind == "collect_watchlist":
                    self._job_collect_watchlist(run_id, j)
                elif kind == "collect_category":
                    self._job_collect_category(run_id, j)
                elif kind == "reconcile_orders":
                    self._job_reconcile_orders(run_id, j)
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
