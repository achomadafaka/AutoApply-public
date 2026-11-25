# HTTP API

The source of truth is the local generated OpenAPI schema: `GET /openapi.json` or `/docs`. By default the application endpoints are under `/v1` and the health check is `GET /health`.

The API exposes job CRUD/import, optional AI analysis and materials, application runs and history, selector metadata, profile answers, and local settings. A browser run can only be started for a configured supported hosted Greenhouse job in `fill_review` mode. Manual tracking uses the existing `assisted` API mode. New `auto` records are rejected; legacy records may still be read. Only manual tracking supports marking an application complete by hand; Fill & Review requires observed employer receipt.
