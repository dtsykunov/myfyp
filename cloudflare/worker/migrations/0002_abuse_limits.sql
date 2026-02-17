CREATE TABLE IF NOT EXISTS abuse_ip_rate_limit (
  ip_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  window_start TEXT NOT NULL,
  request_count INTEGER NOT NULL,
  PRIMARY KEY (ip_hash, action, window_start)
);

CREATE INDEX IF NOT EXISTS idx_abuse_rate_window_start
ON abuse_ip_rate_limit (window_start);

CREATE INDEX IF NOT EXISTS idx_abuse_write_daily_quota_date
ON abuse_ip_write_daily (quota_date);
