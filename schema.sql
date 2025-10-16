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
  run_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  action_type TEXT NOT NULL,
  payload_json TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_actions_run ON actions_log(run_id);
