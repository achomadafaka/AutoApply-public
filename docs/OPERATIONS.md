# Local operations

Stop both services before backing up or restoring. Back up the configured SQLite database and any journal files, settings, answers, artifacts and the local dotenv file to a protected location. The defaults are under `backend/data/` and `backend/artifacts/`. The configured résumé may be stored elsewhere; back it up separately. Preserve file permissions and never include backups in a public repository.

To try an empty workspace without changing existing data, set `AUTOAPPLY_DB_PATH` to a new file and launch the app. Optional demo data belongs in a separate database and is fictional. If a Fill & Review run is unconfirmed after a restart, check without resubmitting.

When reporting an issue, include runtime versions and exact steps with a synthetic example, not private logs or your real résumé.
