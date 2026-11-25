# Testing

```sh
make install
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
make browser-install
make check
```

Tests cover an empty startup, SQLite migration rollback, the loopback request boundary, public job metadata parsing, rate limits, receipt tracking and the headed-runner logic replayed in a headless Chromium fixture. No real profile, employer submission, external job site, or Ollama model is needed. The browser tests load local or intercepted synthetic forms and verify that Fill & Review never sends them.

If browser dependencies were not installed, the browser module is skipped. For release verification and CI, install Chromium and require those tests to run. For a browser smoke check from the repository root, start the app with a fresh database, then run `backend/.venv/bin/python scripts/smoke_ui.py`. It saves, opens and deletes only its own fictional example job.
