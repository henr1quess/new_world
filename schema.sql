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

-- === ORDENS DO BOT ===
CREATE TABLE IF NOT EXISTS my_orders (
  my_order_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id        INTEGER,                               -- run que abriu a ordem (opcional)
  item_name     TEXT NOT NULL,
  side          TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  price         REAL NOT NULL,
  qty_requested INTEGER NOT NULL,
  qty_filled    INTEGER NOT NULL DEFAULT 0,
  status        TEXT NOT NULL DEFAULT 'PENDING',       -- PENDING|ACTIVE|PARTIAL|FILLED|CANCELLED|FAILED|EXPIRED
  settlement    TEXT,                                  -- cidade/local (se quiser)
  placed_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at  TEXT,                                  -- última vez que “vi” a ordem no My Orders
  expires_at    TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_my_orders_active ON my_orders(status, item_name, side);
CREATE INDEX IF NOT EXISTS idx_my_orders_last_seen ON my_orders(last_seen_at);

CREATE TABLE IF NOT EXISTS order_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  my_order_id  INTEGER NOT NULL,
  ts           TEXT NOT NULL DEFAULT (datetime('now')),
  event        TEXT NOT NULL,                          -- PLACED|SEEN|FILL|CANCELLED|EXPIRED|FAILED|CLOSE
  qty_delta    INTEGER,                                -- positivo para fill
  status_after TEXT,                                   -- status após o evento
  details      TEXT,
  FOREIGN KEY (my_order_id) REFERENCES my_orders(my_order_id)
);
CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(my_order_id, ts);

-- Snapshots do tab "My Orders" que leremos via OCR (para conciliação)
CREATE TABLE IF NOT EXISTS my_orders_snapshots (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           TEXT NOT NULL,
  item_name    TEXT NOT NULL,
  side         TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  price        REAL NOT NULL,
  qty_remaining INTEGER,
  settlement   TEXT
);
CREATE INDEX IF NOT EXISTS idx_my_orders_snapshots ON my_orders_snapshots(ts, item_name, side);

-- === INVENTÁRIO (por local) ===
CREATE TABLE IF NOT EXISTS inventory (
  item_name  TEXT NOT NULL,
  location   TEXT NOT NULL DEFAULT 'unknown',
  qty        INTEGER NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (item_name, location)
);
