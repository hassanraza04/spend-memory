from fastapi import FastAPI

app = FastAPI(title="Spend Memory API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
