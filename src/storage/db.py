import json
from pathlib import Path
import sqlite3
from typing import Any

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


# ---------- Orders ----------
def _serialize_details(details: Any) -> str | None:
    if details is None:
        return None
    if isinstance(details, (dict, list)):
        return json.dumps(details, ensure_ascii=False)
    return str(details)


def _extract_reason(details: Any) -> str | None:
    if isinstance(details, dict):
        reason = details.get("reason")
        if reason is not None:
            return str(reason)
    return None


def _insert_order_event(
    con: sqlite3.Connection,
    order_id: int,
    event_type: str,
    details: Any = None,
) -> None:
    payload = _serialize_details(details)
    con.execute(
        """
        INSERT INTO order_events (order_id, event_type, details)
        VALUES (?, ?, ?)
        """,
        (order_id, event_type, payload),
    )


def create_order(
    con: sqlite3.Connection,
    *,
    item_name: str,
    side: str,
    price: float,
    qty_requested: int,
    run_id: int | None = None,
    settlement: str | None = None,
) -> int:
    side_norm = side.upper()
    if side_norm not in {"BUY", "SELL"}:
        raise ValueError(f"Invalid order side '{side}'. Expected 'BUY' or 'SELL'.")

    qty_requested_int = int(qty_requested)
    if qty_requested_int < 0:
        raise ValueError("qty_requested must be non-negative")

    cur = con.execute(
        """
        INSERT INTO orders (item_name, side, price, qty_requested, run_id, settlement)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (item_name, side_norm, float(price), qty_requested_int, run_id, settlement),
    )
    order_id = cur.lastrowid

    _insert_order_event(
        con,
        order_id,
        "CREATED",
        {
            "item_name": item_name,
            "side": side_norm,
            "price": float(price),
            "qty_requested": qty_requested_int,
            "run_id": run_id,
            "settlement": settlement,
        },
    )
    con.commit()
    return order_id


def set_order_active(
    con: sqlite3.Connection,
    order_id: int,
    details: Any = None,
) -> None:
    payload = _serialize_details(details)
    cur = con.execute(
        """
        UPDATE orders
        SET status='ACTIVE',
            status_reason=NULL,
            status_payload=?,
            status_updated_at=datetime('now'),
            last_seen_at=datetime('now'),
            closed_at=NULL
        WHERE order_id=?
        """,
        (payload, order_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"Order {order_id} not found")
    _insert_order_event(con, order_id, "ACTIVE", details)
    con.commit()


def set_order_closed(
    con: sqlite3.Connection,
    order_id: int,
    status: str,
    details: Any = None,
) -> None:
    status_upper = status.upper()
    if not status_upper:
        raise ValueError("status must be a non-empty string")

    payload = _serialize_details(details)
    reason = _extract_reason(details)
    cur = con.execute(
        """
        UPDATE orders
        SET status=?,
            status_reason=?,
            status_payload=?,
            status_updated_at=datetime('now'),
            last_seen_at=datetime('now'),
            closed_at=COALESCE(closed_at, datetime('now'))
        WHERE order_id=?
        """,
        (status_upper, reason, payload, order_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"Order {order_id} not found")
    _insert_order_event(con, order_id, status_upper, details)
    con.commit()


def update_order_fill(
    con: sqlite3.Connection,
    order_id: int,
    qty_delta_filled: int,
) -> int:
    delta = int(qty_delta_filled)
    if delta <= 0:
        raise ValueError("qty_delta_filled must be positive")

    cur = con.execute(
        "SELECT qty_requested, qty_filled FROM orders WHERE order_id=?",
        (order_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Order {order_id} not found")

    qty_requested, qty_filled = row
    new_qty_filled = qty_filled + delta
    if qty_requested is not None and new_qty_filled > qty_requested:
        new_qty_filled = qty_requested

    applied_delta = new_qty_filled - qty_filled
    if applied_delta <= 0:
        con.execute(
            "UPDATE orders SET last_seen_at=datetime('now') WHERE order_id=?",
            (order_id,),
        )
        con.commit()
        return qty_filled

    con.execute(
        """
        UPDATE orders
        SET qty_filled=?,
            status_updated_at=datetime('now'),
            last_seen_at=datetime('now')
        WHERE order_id=?
        """,
        (new_qty_filled, order_id),
    )
    _insert_order_event(
        con,
        order_id,
        "FILL",
        {"qty_delta": applied_delta, "qty_filled": new_qty_filled},
    )
    con.commit()
    return new_qty_filled


def mark_order_seen_now(con: sqlite3.Connection, order_id: int) -> None:
    cur = con.execute(
        "UPDATE orders SET last_seen_at=datetime('now') WHERE order_id=?",
        (order_id,),
    )
    if cur.rowcount == 0:
        raise ValueError(f"Order {order_id} not found")
    con.commit()
