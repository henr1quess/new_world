from __future__ import annotations
import csv
import json
from pathlib import Path

from src.storage.db import ensure_db, upsert_item


def main(csv_path: str = "data/items_catalog.csv"):
    path = Path(csv_path)
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")
    con = ensure_db()
    n = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("item_name") or "").strip()
            if not name:
                continue
            cat = (row.get("category") or "").strip() or None
            sub = (row.get("subcategory") or "").strip() or None
            tags = row.get("tags")
            tags_json = json.dumps([t.strip() for t in tags.split(",") if t.strip()]) if tags else None
            upsert_item(con, name=name, category=cat, subcategory=sub, tags_json=tags_json, source="csv")
            n += 1
    print(f"OK: importados {n} itens.")


if __name__ == "__main__":
    main()
