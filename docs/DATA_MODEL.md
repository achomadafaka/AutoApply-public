# Data Model (SQLite)

## job_listings
- id (text, primary key)
- source (text) manual | import
- title (text)
- company (text)
- location (text)
- url (text)
- description (text)
- requirements (text)
- salary_min (integer)
- salary_max (integer)
- remote (integer) 0 or 1
- status (text) new | applied | archived
- created_at (text, ISO8601)
- updated_at (text, ISO8601)

## job_listings_fts (FTS5)
- title, company, description, requirements

## applications
- id (text, primary key)
- job_id (text, foreign key -> job_listings.id)
- platform (text) greenhouse | lever | other
- mode (text) assisted | auto
- state (text) pending | analyzing_job | generating_materials | awaiting_review | filling_form | submitting | completed | failed
- last_error (text)
- started_at (text, ISO8601)
- completed_at (text, ISO8601)

## application_history
- id (text, primary key)
- application_id (text, foreign key -> applications.id)
- state (text)
- event (text)
- actor (text) system | user
- details_json (text)
- created_at (text, ISO8601)

## resume_versions
- id (text, primary key)
- label (text)
- content_hash (text)
- docx_path (text)
- pdf_path (text)
- created_at (text, ISO8601)

## generated_content
- id (text, primary key)
- job_id (text, foreign key -> job_listings.id)
- resume_version_id (text, foreign key -> resume_versions.id)
- type (text) resume | cover_letter | answer
- content_text (text)
- model_used (text)
- prompt_hash (text)
- rating (integer) 1-5
- created_at (text, ISO8601)

## job_analysis
- id (text, primary key)
- job_id (text, foreign key -> job_listings.id, unique)
- keywords_json (text)
- skills_json (text)
- model_used (text)
- prompt_hash (text)
- created_at (text, ISO8601)

## selector_registry
- id (text, primary key)
- platform (text)
- name (text)
- selectors_json (text)
- success_count (integer)
- failure_count (integer)
- last_success_at (text, ISO8601)
- last_failure_at (text, ISO8601)

## credential_refs
- id (text, primary key)
- service (text)
- username (text)
- keyring_ref (text)
- created_at (text, ISO8601)

## artifacts
- id (text, primary key)
- application_id (text, foreign key -> applications.id)
- type (text) resume_docx | resume_pdf | cover_letter | screenshot | log
- path (text)
- created_at (text, ISO8601)
