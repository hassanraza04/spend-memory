from __future__ import annotations

import os
import subprocess
from pathlib import Path

from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.service import EnrichmentService


class LocalRefreshError(Exception):
    pass


class LocalWorkspaceRefresh:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.project_root = Path(__file__).resolve().parents[3]

    def refresh(self) -> None:
        try:
            self._build_analytics()
            EnrichmentService(EnrichmentRepository(self.database_path)).refresh()
            self._build_analytics()
        except Exception:  # noqa: BLE001
            raise LocalRefreshError from None

    def _build_analytics(self) -> None:
        subprocess.run(
            [
                "uv", "run", "--no-sync", "dbt", "build",
                "--project-dir", "analytics", "--profiles-dir", "analytics",
            ],
            check=True,
            cwd=self.project_root,
            env={**os.environ, "SPEND_MEMORY_DUCKDB_PATH": str(self.database_path)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
