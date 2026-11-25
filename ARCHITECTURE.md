# Architecture

SvelteKit provides the UI, FastAPI serves the local API, and SQLite stores jobs, applications, answers and artifact references. Public Greenhouse and Lever connectors import posting metadata; Ollama is an optional drafting dependency.

Playwright runs only for a single authorized **Fill & Review** session on a supported hosted Greenhouse page. It prefills recognized contact fields only. The applicant attaches documents, answers screening and consent questions, and submits in the browser. AutoApply records a matching, visible employer receipt only after an observed submission attempt.

Legacy run states remain readable. New unattended runs are rejected, and old ones cannot start a browser. See [setup](docs/SETUP.md), [configuration](docs/CONFIG.md), [data model](docs/DATA_MODEL.md) and the live FastAPI schema at `http://127.0.0.1:8000/docs`.
