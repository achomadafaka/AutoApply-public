CREATE TABLE IF NOT EXISTS lever_postings (
  id TEXT PRIMARY KEY,
  site TEXT NOT NULL,
  posting_id TEXT NOT NULL,
  region TEXT NOT NULL DEFAULT 'global',
  payload_json TEXT NOT NULL,
  apply_json TEXT,
  fetched_at TEXT NOT NULL,
  UNIQUE(site, posting_id, region)
);

CREATE INDEX IF NOT EXISTS idx_lever_postings_lookup
  ON lever_postings (site, posting_id, region);
