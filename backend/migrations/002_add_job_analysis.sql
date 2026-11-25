PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS job_analysis (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL UNIQUE,
  keywords_json TEXT NOT NULL,
  skills_json TEXT NOT NULL,
  model_used TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (job_id) REFERENCES job_listings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_analysis_job_id ON job_analysis(job_id);

COMMIT;
