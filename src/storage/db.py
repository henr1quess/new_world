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

# ---------- ORDERS ----------
def create_order(con, *, item_name: str, side: str, price: float, qty_requested: int,
                 run_id: int | None = None, settlement: str | None = None,
                 notes: str | None = None, status: str = "PENDING") -> int:
    cur = con.cursor()
    cur.execute("""
        INSERT INTO my_orders(run_id,item_name,side,price,qty_requested,status,settlement,notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (run_id, item_name, side, price, qty_requested, status, settlement, notes))
    con.commit()
    oid = cur.lastrowid
    append_order_event(con, oid, "PLACED", status_after=status, details=json.dumps({"price":price,"qty":qty_requested}))
    return oid


def set_order_active(con, my_order_id: int) -> None:
    con.execute("UPDATE my_orders SET status='ACTIVE', updated_at=datetime('now') WHERE my_order_id=?", (my_order_id,))
    append_order_event(con, my_order_id, "SEEN", status_after="ACTIVE")
    con.commit()


def update_order_fill(con, my_order_id: int, qty_delta: int) -> None:
    con.execute("""
        UPDATE my_orders SET
          qty_filled = qty_filled + ?,
          status = CASE WHEN qty_filled + ? >= qty_requested THEN 'FILLED'
                        WHEN qty_filled + ? > 0 THEN 'PARTIAL'
                        ELSE status END,
          updated_at = datetime('now')
        WHERE my_order_id = ?
    """, (qty_delta, qty_delta, qty_delta, my_order_id))
    cur = con.execute("SELECT status FROM my_orders WHERE my_order_id=?", (my_order_id,))
    status_after = cur.fetchone()[0]
    append_order_event(con, my_order_id, "FILL", qty_delta=qty_delta, status_after=status_after)
    con.commit()


def set_order_closed(con, my_order_id: int, status: str, details: dict | None = None) -> None:
    con.execute("UPDATE my_orders SET status=?, updated_at=datetime('now') WHERE my_order_id=?",
                (status, my_order_id))
    append_order_event(con, my_order_id, "CLOSE", status_after=status,
                       details=json.dumps(details, ensure_ascii=False) if details else None)
    con.commit()


def mark_order_seen_now(con, my_order_id: int) -> None:
    con.execute("UPDATE my_orders SET last_seen_at=datetime('now'), updated_at=datetime('now') WHERE my_order_id=?",
                (my_order_id,))
    con.commit()


def append_order_event(con, my_order_id: int, event: str, qty_delta: int | None = None,
                       status_after: str | None = None, details: str | None = None) -> None:
    con.execute("""INSERT INTO order_events (my_order_id, event, qty_delta, status_after, details)
                   VALUES (?,?,?,?,?)""", (my_order_id, event, qty_delta, status_after, details))
    con.commit()


def insert_my_order_snapshot(con, row: dict) -> None:
    con.execute("""
        INSERT INTO my_orders_snapshots (ts, item_name, side, price, qty_remaining, settlement)
        VALUES (datetime('now'),?,?,?,?,?)
    """, (row["item_name"], row["side"], row["price"], row.get("qty_remaining"), row.get("settlement")))
    con.commit()


# ---------- INVENTORY ----------
def upsert_inventory(con, *, item_name: str, location: str = "unknown", qty: int) -> None:
    con.execute("""
        INSERT INTO inventory(item_name, location, qty, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(item_name, location) DO UPDATE SET
          qty = excluded.qty,
          updated_at = datetime('now')
    """, (item_name, location, qty))
    con.commit()


def bump_inventory(con, *, item_name: str, location: str = "unknown", qty_delta: int) -> None:
    con.execute("""
        INSERT INTO inventory(item_name, location, qty, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(item_name, location) DO UPDATE SET
          qty = inventory.qty + ?,
          updated_at = datetime('now')
    """, (item_name, location, qty_delta, qty_delta))
    con.commit()
