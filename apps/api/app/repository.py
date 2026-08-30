"""Database-agnostic repository boundary; Phase 1 implementation uses SQLite only."""
from __future__ import annotations

from abc import ABC, abstractmethod
import sqlite3
from pathlib import Path
from typing import Any


class ProjectRepository(ABC):
    @abstractmethod
    def list_projects(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def create_project(self, project_id: str, title: str, premise: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_project(self, project_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def set_rendered(self, project_id: str, asset_id: str, media_path: str) -> None: ...

    @abstractmethod
    def get_asset_path(self, asset_id: str) -> Path | None: ...


class SqliteProjectRepository(ProjectRepository):
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, premise TEXT NOT NULL,
                  production_state TEXT NOT NULL, asset_id TEXT, media_path TEXT
                );
                CREATE TABLE IF NOT EXISTS assets (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, media_path TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def create_project(self, project_id: str, title: str, premise: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects (id, title, premise, production_state) VALUES (?, ?, ?, ?)",
                (project_id, title, premise, "PLANNED"),
            )
        return self.get_project(project_id) or {}

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM projects ORDER BY rowid DESC").fetchall()]
        return [project for project_id in ids if (project := self.get_project(project_id))]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, title, premise, production_state, asset_id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "title": row[1], "premise": row[2], "production_state": row[3], "rough_cut_asset_id": row[4]}

    def set_rendered(self, project_id: str, asset_id: str, media_path: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO assets (id, project_id, media_path) VALUES (?, ?, ?)", (asset_id, project_id, media_path))
            connection.execute(
                "UPDATE projects SET production_state = ?, asset_id = ?, media_path = ? WHERE id = ?",
                ("ROUGH_CUT_READY", asset_id, media_path, project_id),
            )

    def get_asset_path(self, asset_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute("SELECT media_path FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return Path(row[0]) if row else None
