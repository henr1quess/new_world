from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "market.db"


def ensure_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            mode TEXT,
            notes TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prices_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            source_view TEXT,
            item_name TEXT,
            price REAL,
            qty_visible INTEGER,
            page_index INTEGER,
            scroll_pos REAL,
            confidence REAL,
            hash_row TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        )
        """
    )
    con.commit()


def new_run(con: sqlite3.Connection, mode: str, notes: str = "") -> int:
    cur = con.cursor()
    cur.execute("INSERT INTO runs(mode, notes) VALUES (?, ?)", (mode, notes))
    con.commit()
    return cur.lastrowid


def end_run(con: sqlite3.Connection, run_id: int) -> None:
    cur = con.cursor()
    cur.execute("UPDATE runs SET ended_at=CURRENT_TIMESTAMP WHERE id=?", (run_id,))
    con.commit()


def insert_snapshot(con: sqlite3.Connection, run_id: int, data: Dict[str, Any]) -> None:
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO prices_snapshots(
            run_id, timestamp, source_view, item_name, price,
            qty_visible, page_index, scroll_pos, confidence, hash_row
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            data["timestamp"],
            data.get("source_view"),
            data.get("item_name"),
            data.get("price"),
            data.get("qty_visible"),
            data.get("page_index"),
            data.get("scroll_pos"),
            data.get("confidence"),
            data.get("hash_row"),
        ),
    )
    con.commit()
