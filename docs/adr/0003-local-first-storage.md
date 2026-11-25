# ADR 0003: Local-First Storage

Status: accepted

## Context
The system handles sensitive personal data and credentials.
We want minimal operational overhead and maximum privacy.

## Decision
Use SQLite for core data and the local filesystem for artifacts.
Store credentials only via OS keyring references, not plaintext.

## Consequences
- Simple backup and restore (copy the DB and artifact folder).
- Encryption at rest can be added later (SQLCipher).
- No external database dependency in MVP.
