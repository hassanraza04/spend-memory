.PHONY: dev test lint clean-demo

dev:
	docker compose up --build

test:
	UV_CACHE_DIR=.uv-cache uv run pytest
	pnpm --dir apps/web test

lint:
	UV_CACHE_DIR=.uv-cache uv run ruff check apps/api sample_data
	pnpm --dir apps/web lint

clean-demo:
	docker compose down --volumes --remove-orphans
