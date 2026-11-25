PRAGMA foreign_keys = ON;

BEGIN;

INSERT INTO job_listings (
  id, source, title, company, location, url, description, requirements,
  salary_min, salary_max, remote, status, created_at, updated_at
) VALUES (
  'job_1',
  'manual',
  'Backend Engineer',
  'Example Labs',
  'Remote',
  'https://example.com/jobs/123',
  'Build APIs, data pipelines, and automation services.',
  'Python, FastAPI, SQLite, Playwright',
  120000,
  160000,
  1,
  'new',
  datetime('now'),
  datetime('now')
);

INSERT INTO resume_versions (
  id, label, content_hash, docx_path, pdf_path, created_at
) VALUES (
  'res_1',
  'Baseline 2026-01',
  'hash_res_1',
  'artifacts/resumes/baseline.docx',
  'artifacts/resumes/baseline.pdf',
  datetime('now')
);

INSERT INTO generated_content (
  id, job_id, resume_version_id, type, content_text, model_used,
  prompt_hash, rating, created_at
) VALUES (
  'gen_1',
  'job_1',
  'res_1',
  'cover_letter',
  'Cover letter draft for Example Labs.',
  'llama3.1:8b',
  'hash_prompt_1',
  4,
  datetime('now')
);

INSERT INTO applications (
  id, job_id, platform, mode, state, last_error, started_at, completed_at
) VALUES (
  'app_1',
  'job_1',
  'greenhouse',
  'assisted',
  'pending',
  NULL,
  NULL,
  NULL
);

INSERT INTO application_history (
  id, application_id, state, event, actor, details_json, created_at
) VALUES (
  'hist_1',
  'app_1',
  'pending',
  'created',
  'system',
  '{"note":"Application created"}',
  datetime('now')
);

INSERT INTO selector_registry (
  id, platform, name, selectors_json, success_count, failure_count,
  last_success_at, last_failure_at
) VALUES (
  'sel_1',
  'greenhouse',
  'apply_button',
  '["[data-automation-id=\\"apply-button\\"]","button:has-text(\\"Apply\\")"]',
  3,
  0,
  datetime('now'),
  NULL
);

INSERT INTO credential_refs (
  id, service, username, keyring_ref, created_at
) VALUES (
  'cred_1',
  'greenhouse',
  'user@example.com',
  'keyring://autoapply/greenhouse/user@example.com',
  datetime('now')
);

INSERT INTO artifacts (
  id, application_id, type, path, created_at
) VALUES (
  'art_1',
  'app_1',
  'screenshot',
  'artifacts/screenshots/app_1_start.png',
  datetime('now')
);

COMMIT;
