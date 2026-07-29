# Spend Memory

Spend Memory is a small monorepo with a Next.js web app and a FastAPI service.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 24 and pnpm 11.9.0
- Tesseract OCR 5 with English language data for local OCR tests
- Docker Compose for the full local stack

Install Tesseract on macOS with `brew install tesseract`. On Ubuntu or Debian,
use `sudo apt-get update && sudo apt-get install --yes tesseract-ocr`. Confirm
the executable is available with `tesseract --version`. The API container
already installs the same package during its image build.

## Development

Install the exact locked dependencies, then run checks:

```sh
uv sync --locked
pnpm install --frozen-lockfile
make test
make lint
```

Use `make dev` to build and start the stack. The web app is bound to `127.0.0.1:3000` and the API health endpoint is at `http://127.0.0.1:8000/health`. DuckDB data is retained in the local `duckdb_data` Docker volume. Use `make clean-demo` to stop the stack and remove that demo volume.

Import storage uses `fcntl` advisory file locks. A database-level lock beside
the DuckDB file coordinates every local writer, including imports of different
statement documents. Per-document locks in the configured data directory also
make exact retries idempotent and protect original-file replacement. This is
supported on macOS, Linux, and the Linux Docker runtime used by this project.
Windows is not a supported local runtime.

PDF structural inspection, statement parser detection, and extraction run in
local spawned processes. Each worker has a 25 CPU-second limit and can hold at
most 64 file descriptors. Linux workers also have a 1.5 GiB address-space
limit. macOS does not apply
`RLIMIT_AS`: its Python runtime maps system shared memory before the worker
starts, so the kernel rejects a lower address-space limit. Parser extraction
results are capped at 10,000 transactions before the API reads them. Limit
breaches return safe import errors and never expose parser details.

`IngestionService.import_document` is the only supported production entry point
for statement bytes. It validates each document before using the registry's
isolated parser worker. Direct parser calls are limited to trusted parser unit
tests outside that worker; the registry does not expose public direct selection
or parsing methods. `ImportRepository.store_preparsed_document` is a lower-level
persistence boundary for already isolated `ParsedRawTransaction` output. It
never selects or runs a parser. Native PDF text extraction and Tesseract OCR
helpers are private parser-worker helpers, not production entry points.

When a caller retries a known parser result, it passes that parser's stable ID
and version to `import_document`. Spend Memory then checks the document SHA-256
and parser identity before starting a worker. An exact stored run is returned
without parser detection or extraction. A new parser version proceeds through
the normal isolated parsing path.

## Branch convention

`main` remains stable. Normal work uses `feature/<short-name>`. Use isolated Git worktrees for parallel or high-risk changes. The tracked `.githooks/pre-push` hook rejects non-fast-forward pushes to `main`; enable it locally with:

```sh
git config core.hooksPath .githooks
```
