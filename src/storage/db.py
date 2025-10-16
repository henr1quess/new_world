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
    _migrate_items_catalog_to_items(con)
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


# ---------- Catálogo ----------
def upsert_item(
    con,
    *,
    name: str,
    category: str | None = None,
    subcategory: str | None = None,
    tags_json: str | None = None,
    source: str | None = None,
):
    source_insert = source if source is not None else "manual"
    con.execute(
        """
        INSERT INTO items (name, category, subcategory, tags, source, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(name) DO UPDATE SET
            category=COALESCE(excluded.category, items.category),
            subcategory=COALESCE(excluded.subcategory, items.subcategory),
            tags=COALESCE(excluded.tags, items.tags),
            source=COALESCE(?, items.source),
            updated_at=datetime('now')
        """,
        (name, category, subcategory, tags_json, source_insert, source),
    )
    con.commit()


# ---------- Migração: items_catalog -> items ----------
def _has_table(con, name: str) -> bool:
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def _migrate_items_catalog_to_items(con):
    """Migra dados da tabela legada ``items_catalog`` para ``items`` se necessário."""
    if not _has_table(con, "items_catalog"):
        return

    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
          item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          category TEXT,
          subcategory TEXT,
          tags TEXT,
          source TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT
        );
        """
    )

    con.execute(
        """
        INSERT INTO items (name, category, subcategory, tags, source, created_at, updated_at)
        SELECT name, category, subcategory, tags_json, source, datetime('now'), COALESCE(updated_at, datetime('now'))
        FROM items_catalog
        ON CONFLICT(name) DO UPDATE SET
          category=excluded.category,
          subcategory=excluded.subcategory,
          tags=excluded.tags,
          source=excluded.source,
          updated_at=excluded.updated_at;
        """
    )

    con.execute("DROP TABLE items_catalog")
    con.commit()
