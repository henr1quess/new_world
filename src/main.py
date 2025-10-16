import json
import time
from pathlib import Path
from typing import List

import typer

from src.capture.scroll import focus_and_scroll_one_page
from src.exec.nav import open_item_by_search
from src.ocr.extract import scan_once
from src.storage.db import end_run, ensure_db, insert_snapshot, new_run

app = typer.Typer(add_completion=False)

BASE = Path(__file__).resolve().parents[1]
CFG_OCR = BASE / "config" / "ocr.yaml"
CFG_UI = BASE / "config" / "ui_profiles.yaml"


def _load_watchlist(path: Path) -> List[str]:
    if not path.exists():
        raise typer.BadParameter(f"Arquivo não encontrado: {path}")

    items: List[str] = []
    with path.open("r", encoding="utf-8-sig") as fh:
        for line in fh:
            name = line.strip()
            if not name:
                continue
            if not items and name.lower() == "item_name":
                # Ignore optional header row.
                continue
            items.append(name)

    if not items:
        raise typer.BadParameter("Watchlist vazia — adicione ao menos um item.")

    return items


@app.command()
def scan(
    source_view: str = typer.Option("BUY_LIST", help="BUY_LIST ou SELL_LIST"),
    pages: int = typer.Option(3, help="quantas páginas (scrolls) estimar"),
    out_json: str = typer.Option("", help="salvar também em JSON (opcional)"),
):
    """Nível 0: captura uma amostra da lista (12 linhas por página) e salva no SQLite."""
    con = ensure_db()
    run_id = new_run(con, mode="scan", notes=f"{source_view}")
    all_rows = []
    try:
        for p in range(pages):
            rows = scan_once(
                source_view,
                str(CFG_OCR),
                str(CFG_UI),
                page_index=p,
                scroll_pos=p,
            )
            for r in rows:
                insert_snapshot(con, run_id, r)
            all_rows.extend(rows)

            if p < pages - 1:
                # rolar para a próxima "página" da lista (exceto após a última)
                focus_and_scroll_one_page(str(CFG_UI))
        if out_json:
            Path(out_json).write_text(
                json.dumps(all_rows, indent=2), encoding="utf-8"
            )
    finally:
        end_run(con, run_id)


@app.command()
def scan_watchlist(
    source_view: str = typer.Option("BUY_LIST", help="BUY_LIST ou SELL_LIST"),
    watchlist_csv: str = typer.Option(..., help="arquivo CSV com uma coluna 'item_name'"),
    pages: int = typer.Option(1, help="quantas páginas ler por item"),
    out_json: str = typer.Option("", help="salvar também em JSON (opcional)"),
):
    """Varre a watchlist digitando no campo de busca antes de capturar os preços."""

    items = _load_watchlist(Path(watchlist_csv))

    con = ensure_db()
    run_id = new_run(
        con,
        mode="scan_watchlist",
        notes=f"{source_view}|watchlist={Path(watchlist_csv).name}",
    )
    all_rows = []
    page_counter = 0

    try:
        for item in items:
            open_item_by_search(str(CFG_UI), item)
            time.sleep(0.4)

            scroll_pos = 0.0
            for page in range(pages):
                rows = scan_once(
                    source_view,
                    str(CFG_OCR),
                    str(CFG_UI),
                    page_index=page_counter,
                    scroll_pos=scroll_pos,
                )
                for r in rows:
                    insert_snapshot(con, run_id, r)
                all_rows.extend(rows)

                page_counter += 1
                scroll_pos += 1

                if page < pages - 1:
                    focus_and_scroll_one_page(str(CFG_UI))
                    time.sleep(0.3)

        if out_json:
            Path(out_json).write_text(
                json.dumps(all_rows, indent=2), encoding="utf-8"
            )
    finally:
        end_run(con, run_id)


@app.command()
def dashboard():
    """Abre o dashboard Streamlit (Nível 0)."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(BASE / "streamlit_app.py")]
    )


if __name__ == "__main__":
    app()
