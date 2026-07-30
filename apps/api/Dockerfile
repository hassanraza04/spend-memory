FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.11.27

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY apps/api ./apps/api

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
