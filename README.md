# AutoApply

A local job search workspace. Save a posting, keep your notes and application materials together, and track what you sent. For supported Greenhouse forms, **Fill & Review** opens a visible browser, prefills recognized contact fields, and stops. You attach your résumé and answer all employer questions yourself. **You review and submit the form yourself.**

## What works today

| Workflow | Support |
| --- | --- |
| Save, track and import jobs | Manual entries, plus public Greenhouse and Lever job data |
| Draft application materials | Optional local Ollama; generated text always needs review |
| Fill one application | Compatible hosted Greenhouse forms; requires Playwright and a graphical desktop |
| Send an application | Manual only. No background submission, account login, or CAPTCHA solving |
| Track the result | The browser runner records completion only after a known matching employer receipt; otherwise the result stays unconfirmed |

The app is single-user and has no login. Run it on your own computer, not on a public server or a shared network. Only use form assistance where allowed by the employer and platform.

## Quick start

On Linux or macOS, install **Python 3.11**, **Node.js 24**, and **GNU Make**. The combined launcher needs **Bash 4.3+** (macOS users can install modern Bash or run the API and UI separately). From the repository root:

```sh
make install
./dev-review.sh
```

Open [AutoApply](http://localhost:5173) and go to **Jobs** to add one. SQLite is initialized automatically; the first run starts empty. To load fictional examples in an empty database, run `make demo` before starting the app. No account, model download, or browser install is needed for manual tracking.

## Enable Fill & Review

1. Run `make browser-install`. On Linux, if Chromium reports missing system libraries, run `backend/.venv/bin/python -m playwright install-deps chromium` after reviewing the system changes.
2. Copy `backend/.env.example` to `backend/.env`. Set `AUTOAPPLY_AUTOMATION_ENABLED=true`, enter your first name, last name and email, and point `AUTOAPPLY_PROFILE_RESUME_PATH` at an **absolute path** to the résumé you want to send. Restart the launcher.
3. Save a hosted Greenhouse job. Create a **Fill & Review** run from the job page, then start it from the run page. Confirm the employer destination and every answer, then upload the exact reviewed file and press Submit yourself. Complete consent and any verification in the employer’s window.

Selecting a file in a form can upload it before submission. Use a tailored, reviewed document and don't use an employer's live form to test the app. The tests use fictional profiles and intercepted browser fixtures instead.

## Learn more

- [Setup and troubleshooting](docs/SETUP.md)
- [Configuration](docs/CONFIG.md) and [what leaves your machine](docs/SECURITY.md)
- [Testing](docs/TESTING.md)
- [Architecture](ARCHITECTURE.md) and [release checklist](docs/RELEASE_CHECKLIST.md)

License: no open-source license has been granted yet.
