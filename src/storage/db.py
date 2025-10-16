import json
from pathlib import Path
import sqlite3

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "market.db"


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        con.executescript(f.read())
    con.commit()
    return con


def new_run(con, mode="scan", notes=None):
    cur = con.cursor()
    cur.execute(
        "INSERT INTO runs (started_at, mode, notes) VALUES (datetime('now'), ?, ?)",
        (mode, notes),
    )
    con.commit()
    return cur.lastrowid


def end_run(con, run_id):
    con.execute("UPDATE runs SET ended_at=datetime('now') WHERE run_id=?", (run_id,))
    con.commit()


def insert_snapshot(con, run_id, row):
    con.execute(
        """
        INSERT INTO prices_snapshots
        (run_id, timestamp, source_view, item_name, price, qty_visible, page_index, scroll_pos, confidence, hash_row)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            row["timestamp"],
            row["source_view"],
            row["item_name"],
            row["price"],
            row.get("qty_visible"),
            row.get("page_index"),
            row.get("scroll_pos"),
            row.get("confidence"),
            row.get("hash_row"),
        ),
    )
    con.commit()


def insert_action(con, run_id, action, details=None, success=1, notes=None):
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=False)
    con.execute(
        """
        INSERT INTO actions_log (ts, run_id, action, details, success, notes)
        VALUES (datetime('now'), ?, ?, ?, ?, ?)
        """,
        (run_id, action, details, success, notes),
    )
    con.commit()


def upsert_item(con, *, name, category=None, subcategory=None, tags_json=None, source=None):
    con.execute(
        """
        INSERT INTO items_catalog (name, category, subcategory, tags_json, source, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(name) DO UPDATE SET
            category=excluded.category,
            subcategory=excluded.subcategory,
            tags_json=excluded.tags_json,
            source=excluded.source,
            updated_at=datetime('now')
        """,
        (name, category, subcategory, tags_json, source),
    )
    con.commit()
