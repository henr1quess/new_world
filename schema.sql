PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  mode TEXT NOT NULL,               -- 'scan'
  notes TEXT
);

CREATE TABLE IF NOT EXISTS prices_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  timestamp TEXT NOT NULL,
  source_view TEXT NOT NULL,        -- 'BUY_LIST' | 'SELL_LIST'
  item_name TEXT NOT NULL,
  price REAL NOT NULL,
  qty_visible INTEGER,
  page_index INTEGER,
  scroll_pos REAL,
  confidence REAL,
  hash_row TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_item_time ON prices_snapshots(item_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_prices_source ON prices_snapshots(source_view);

CREATE TABLE IF NOT EXISTS actions_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  run_id INTEGER,
  action TEXT NOT NULL,
  details TEXT,
  success INTEGER DEFAULT 1,
  notes TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions_log(ts);
CREATE INDEX IF NOT EXISTS idx_actions_run ON actions_log(run_id);

-- Catálogo de itens (para categorias, tags e organização de coletas)
-- Padronizado para a tabela `items` após limpeza de marcadores de merge.
CREATE TABLE IF NOT EXISTS items (
  item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  category TEXT,
  subcategory TEXT,
  tags TEXT,              -- JSON: ["hot","flip_candidate"]
  source TEXT,            -- 'csv' | 'ocr' | 'manual' | 'wiki'
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT         -- atualizado manualmente conforme necessário
);

CREATE INDEX IF NOT EXISTS idx_items_cat ON items(category, subcategory);

CREATE TABLE IF NOT EXISTS orders (
  order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  closed_at TEXT,
  last_seen_at TEXT,
  item_name TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  price REAL NOT NULL,
  qty_requested INTEGER NOT NULL CHECK (qty_requested >= 0),
  qty_filled INTEGER NOT NULL DEFAULT 0 CHECK (qty_filled >= 0),
  status TEXT NOT NULL DEFAULT 'CREATED',
  status_reason TEXT,
  status_payload TEXT,
  status_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  run_id INTEGER,
  settlement TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_run ON orders(run_id);
CREATE INDEX IF NOT EXISTS idx_orders_item ON orders(item_name);

CREATE TABLE IF NOT EXISTS order_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  event_type TEXT NOT NULL,
  details TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id);
