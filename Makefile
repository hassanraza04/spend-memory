.PHONY: dev test lint clean-demo analytics analytics-test

dev:
	docker compose up --build

test:
	UV_CACHE_DIR=.uv-cache uv run pytest
	pnpm --dir apps/web test

lint:
	UV_CACHE_DIR=.uv-cache uv run ruff check apps/api sample_data
	pnpm --dir apps/web lint

analytics:
	SPEND_MEMORY_DUCKDB_PATH=$${SPEND_MEMORY_DUCKDB_PATH:?set a local DuckDB path} uv run dbt build --project-dir analytics --profiles-dir analytics

analytics-test:
	uv run pytest apps/api/tests/test_analytics_models.py -v

clean-demo:
	docker compose down --volumes --remove-orphans
