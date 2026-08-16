# Privacy

Spend Memory is a local learning project. It is not a hosted financial service.

## What stays on the device

- Original imported statements are stored in the configured local data directory.
- Raw transactions, trusted analytics, corrections, and review signals are stored in the local DuckDB database.
- The browser stores only small interface preferences, such as the selected theme, table preset, and whether the synthetic demo was opened. It does not store statement contents in browser storage.
- OCR, parser selection, analytics, merchant matching, search, and spending explanations run locally.

The application does not include authentication, cloud storage, bank connections, payments, hosted inference, analytics trackers, or remote merchant lookups. dbt anonymous usage telemetry is disabled in the checked-in analytics profile.

## Network boundaries

The API and web application bind to `127.0.0.1` in Docker Compose. The web application proxies only to an allowlisted local API origin. The API has no permissive CORS policy. Browser-originated `POST`, `PATCH`, and `DELETE` requests must come from the local web application at `http://127.0.0.1:3000` or `http://localhost:3000`.

Terminal tools may call the local API without an `Origin` header. This is intentional for local development and does not make the API remotely reachable. A process already running on the same device is outside the browser-origin boundary and must be trusted as part of the local operating-system account.

## Imports and logs

Statement ingress validates filenames, MIME types, document sizes, and PDF structure before parser detection. Parsing and OCR run in limited local worker processes. Safe API errors do not return document bytes, raw descriptions, filenames, paths, SQL, or worker details.

Normal application logs must not include request bodies, document bytes, raw descriptions, or full filenames. The committed CI workflow uses only synthetic fixtures. Do not run CI or share debug logs with real statements.

## Retention and deletion

`DELETE /api/v1/local-data` requires the exact confirmation `DELETE LOCAL DATA`. It removes the configured statement data directory and local DuckDB database after path and writer-lock checks. `make clean-demo` runs `docker compose down --volumes --remove-orphans`, which removes the Docker data volume. Either action can remove real imports, so use it only when you mean to clear the whole local workspace.

Deletion cannot remove copies a person made outside Spend Memory, including downloaded CSV exports, backups, screenshots, or manually copied logs.

## Source control and scanners

Real statements and local application data are ignored by Git. Only deterministic synthetic statements are committed. GitHub security scans inspect repository source code and dependency lockfiles. They must never be pointed at a directory containing real financial data.

Any future hosted demo must contain synthetic data only and must disable uploads in both the interface and API.
