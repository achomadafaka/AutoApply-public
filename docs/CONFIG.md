# Configuration

Copy the tracked [backend environment template](../backend/.env.example) to `backend/.env`. Never commit the populated file. Restart the API after changes. Frontend overrides go in `frontend/.env`; see its [template](../frontend/.env.example).

| Setting | Purpose |
| --- | --- |
| `AUTOAPPLY_DB_PATH`, `AUTOAPPLY_SETTINGS_PATH` | Local database and settings paths; default under `backend/data/` in the standard launcher |
| `AUTOAPPLY_CORS_ORIGINS` | Comma-separated local UI origins; keep loopback only |
| `AUTOAPPLY_DAILY_LIMIT` | Limit new runs per UTC day, 1–200. Existing run retries do not consume another slot |
| `AUTOAPPLY_AUTOMATION_ENABLED` and `AUTOAPPLY_AUTOMATION_DRIVER` | Browser fill is disabled by default; set enabled to true and driver to `playwright` after installing Chromium |
| `AUTOAPPLY_AUTOMATION_INTERACTIVE_TIMEOUT_SEC` | How long the review window stays open (default 1800 seconds) |
| `AUTOAPPLY_PROFILE_*` | Explicit applicant details and document paths. Nothing is inferred or treated as verified by the app |
| `OLLAMA_BASE_URL`, `OLLAMA_ANALYZE_MODEL`, `OLLAMA_GENERATE_MODEL`, `OLLAMA_TIMEOUT_SEC` | Optional local drafting/analysis configuration |

To keep personal answer notes outside the employer form, point `AUTOAPPLY_PROFILE_ANSWERS_PATH` at a private JSON file. Example with fictional content:

```json
{
  "greenhouse": {
    "When can you start?": "After notice period"
  }
}
```

Fill & Review does not use saved answers, including API-supplied screening answers. Review country, consent, work authorization, required fields, and document choices yourself. Previously configured automatic-submission or generic interaction toggles are no longer supported.

## Private CV workspace

Set `AUTOAPPLY_CV_WORKSPACE` to an ignored local directory. Put each reviewed source in `baselines/` as matching `topic-name.pdf` (preview for manual upload) and `topic-name.txt` (text evidence for drafts). A job's detail page lets you choose a baseline for drafting; the application page offers a separate PDF choice with an explicit review checkbox. This is a local preview and reminder only. Upload the file yourself on the employer form. Never point the app at a public folder.

To use your own drafting rules, create `protocols/DRAFTING.md` in the same directory. The app uses those rules with local Ollama only. Employer text is input evidence, not instructions. Keep application-specific CVs under `references/` if you want an archive; the app deliberately does not use them as reusable claims or attach them automatically.
