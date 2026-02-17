CREATE TABLE IF NOT EXISTS snapshots (
  hash TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_expires_at
ON snapshots (expires_at);

CREATE TABLE IF NOT EXISTS abuse_ip_write_daily (
  ip_hash TEXT NOT NULL,
  quota_date TEXT NOT NULL,
  write_count INTEGER NOT NULL,
  PRIMARY KEY (ip_hash, quota_date)
);
