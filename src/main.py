import json
from pathlib import Path

import typer

from src.ocr.extract import scan_once
from src.storage.db import end_run, ensure_db, insert_snapshot, new_run

app = typer.Typer(add_completion=False)

BASE = Path(__file__).resolve().parents[1]
CFG_OCR = BASE / "config" / "ocr.yaml"
CFG_UI = BASE / "config" / "ui_profiles.yaml"


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
