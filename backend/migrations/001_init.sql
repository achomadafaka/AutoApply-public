PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE job_listings (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  location TEXT,
  url TEXT,
  description TEXT,
  requirements TEXT,
  salary_min INTEGER,
  salary_max INTEGER,
  remote INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE job_listings_fts USING fts5(
  title,
  company,
  description,
  requirements,
  content='job_listings',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

CREATE TRIGGER job_listings_ai AFTER INSERT ON job_listings BEGIN
  INSERT INTO job_listings_fts(rowid, title, company, description, requirements)
  VALUES (new.rowid, new.title, new.company, new.description, new.requirements);
END;

CREATE TRIGGER job_listings_ad AFTER DELETE ON job_listings BEGIN
  INSERT INTO job_listings_fts(job_listings_fts, rowid, title, company, description, requirements)
  VALUES ('delete', old.rowid, old.title, old.company, old.description, old.requirements);
END;

CREATE TRIGGER job_listings_au AFTER UPDATE ON job_listings BEGIN
  INSERT INTO job_listings_fts(job_listings_fts, rowid, title, company, description, requirements)
  VALUES ('delete', old.rowid, old.title, old.company, old.description, old.requirements);
  INSERT INTO job_listings_fts(rowid, title, company, description, requirements)
  VALUES (new.rowid, new.title, new.company, new.description, new.requirements);
END;

CREATE TABLE applications (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  mode TEXT NOT NULL,
  state TEXT NOT NULL,
  last_error TEXT,
  started_at TEXT,
  completed_at TEXT,
  FOREIGN KEY (job_id) REFERENCES job_listings(id) ON DELETE CASCADE
);

CREATE TABLE application_history (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL,
  state TEXT NOT NULL,
  event TEXT NOT NULL,
  actor TEXT NOT NULL,
  details_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE resume_versions (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  docx_path TEXT,
  pdf_path TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE generated_content (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  resume_version_id TEXT NOT NULL,
  type TEXT NOT NULL,
  content_text TEXT NOT NULL,
  model_used TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  rating INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (job_id) REFERENCES job_listings(id) ON DELETE CASCADE,
  FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE CASCADE
);

CREATE TABLE selector_registry (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  name TEXT NOT NULL,
  selectors_json TEXT NOT NULL,
  success_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  last_success_at TEXT,
  last_failure_at TEXT
);

CREATE TABLE credential_refs (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  username TEXT NOT NULL,
  keyring_ref TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL,
  type TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE INDEX idx_job_listings_status ON job_listings(status);
CREATE INDEX idx_applications_job_id ON applications(job_id);
CREATE INDEX idx_application_history_app_id ON application_history(application_id);
CREATE INDEX idx_generated_content_job_id ON generated_content(job_id);
CREATE INDEX idx_generated_content_resume_id ON generated_content(resume_version_id);
CREATE INDEX idx_artifacts_app_id ON artifacts(application_id);

COMMIT;
