from pathlib import Path

from app.main import LOCAL_API_HOST, run_local_api
from spend_memory.api.dependencies import LocalSettings, load_local_settings


def test_local_settings_default_to_local_paths(monkeypatch) -> None:
    monkeypatch.delenv("DUCKDB_PATH", raising=False)
    monkeypatch.delenv("SPEND_MEMORY_DATA_DIRECTORY", raising=False)

    assert load_local_settings() == LocalSettings(
        Path("spend-memory.duckdb"), Path("data"), Path(".")
    )


def test_local_settings_preserve_the_compose_data_volume(monkeypatch) -> None:
    monkeypatch.setenv("DUCKDB_PATH", "/data/spend-memory.duckdb")
    monkeypatch.setenv("SPEND_MEMORY_DATA_DIRECTORY", "/data/documents")

    assert load_local_settings() == LocalSettings(
        Path("/data/spend-memory.duckdb"), Path("/data/documents"), Path("/data")
    )


def test_normal_local_execution_uses_loopback(monkeypatch) -> None:
    calls: list[tuple[object, str, int]] = []

    monkeypatch.setattr(
        "app.main.uvicorn.run",
        lambda app, host, port: calls.append((app, host, port)),
    )

    run_local_api()

    assert LOCAL_API_HOST == "127.0.0.1"
    assert calls[0][1:] == ("127.0.0.1", 8000)
