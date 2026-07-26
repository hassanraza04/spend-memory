# Spend Memory

Spend Memory is a small monorepo with a Next.js web app and a FastAPI service.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 24 and pnpm 11.9.0
- Docker Compose for the full local stack

## Development

Install the exact locked dependencies, then run checks:

```sh
uv sync --locked
pnpm install --frozen-lockfile
make test
make lint
```

Use `make dev` to build and start the stack. The web app is bound to `127.0.0.1:3000` and the API health endpoint is at `http://127.0.0.1:8000/health`. DuckDB data is retained in the local `duckdb_data` Docker volume. Use `make clean-demo` to stop the stack and remove that demo volume.

## Branch convention

`main` remains stable. Normal work uses `feature/<short-name>`. Use isolated Git worktrees for parallel or high-risk changes. The tracked `.githooks/pre-push` hook rejects non-fast-forward pushes to `main`; enable it locally with:

```sh
git config core.hooksPath .githooks
```

