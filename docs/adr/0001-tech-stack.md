# ADR 0001: Tech Stack Selection

Status: accepted

## Context
We need a local-first system for job application automation that balances
reliability while preserving applicant review and supports local LLM inference.

## Decision
Use Playwright + FastAPI + Ollama + Svelte + SQLite.

## Rationale
- Playwright offers robust automation for modern SPAs and good stealth tooling.
- FastAPI integrates well with Python automation and LLM tooling.
- Ollama enables local model hosting with manageable VRAM footprints.
- Svelte provides a fast, lightweight UI for a local dashboard.
- SQLite is zero-config and ideal for single-user local storage.

## Consequences
- Python is the main backend language.
- We design for local deployment, not multi-tenant cloud.
- UI and API are decoupled and can evolve independently.
