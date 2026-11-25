# Setup

From the root, use `make install`, then `./dev-review.sh`. The API listens at `127.0.0.1:8000`; the UI is at `http://localhost:5173`. Stop both with Ctrl+C. In separate terminals, use `make api-dev` and `make ui-dev`.

- **Python:** 3.11; if multiple interpreters are installed, use `make PYTHON=python3.11 install`.
- **Node.js:** 24; `nvm use` reads `.nvmrc`.
- **Browser:** optional, `make browser-install`. Fill & Review runs in a visible Chromium session and requires a graphical desktop.
- **Data:** The API applies SQLite migrations on launch and preserves existing records. With the documented launcher, relative paths in the backend config are relative to `backend/`. To back up a database, stop AutoApply first and back up the data directory. Restore only to a stopped instance.
- **Ports:** set `AUTOAPPLY_API_PORT` or `AUTOAPPLY_UI_PORT` before running the combined launcher when defaults are busy.
- **Models:** no model needed for the tracking workflow. For local analysis and drafting, run Ollama, install the chosen models (e.g. `ollama pull llama3.1:8b` and `ollama pull qwen2.5:7b`) and review the model status in the dashboard. Job analysis can fall back to heuristics; résumé and cover letter drafting requires Ollama and will report a clear error if no draft is returned. Set AUTOAPPLY_PROFILE_BASE_RESUME_PATH to your reviewed TXT, Markdown or DOCX baseline.

## Troubleshooting

- **Moved directory or broken venv:** Remove or move the old virtual environment, not the `data/` or `artifacts/` directories. Re-run `make PYTHON=python3.11 install`, then reinstall Chromium support if you use it.
- **Fill & Review blocked:** verify the app has Playwright, a Chromium binary and a desktop display; confirm the saved profile and a supported Greenhouse URL. Select and upload the final CV manually.
- **Browser closed without confirmation:** check the employer's page or your inbox before trying to apply again. Lack of confirmation is not evidence the employer received nothing.
