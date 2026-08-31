"""Database-agnostic repository boundary; Phase 1 implementation uses SQLite only."""
from __future__ import annotations

from abc import ABC, abstractmethod
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from .config import DATABASE_PATH, DATABASE_URL, ENVIRONMENT, POSTGRES_REQUIRED_ENVIRONMENTS
from .db import asset, asset_version, project, workspace


LOCAL_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


class ProjectRepository(ABC):
    @property
    @abstractmethod
    def persistence_name(self) -> str: ...

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

    @property
    def persistence_name(self) -> str:
        return "sqlite-local"

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


class PostgresProjectRepository(ProjectRepository):
    """Production repository. Schema creation is exclusively managed by Alembic."""

    def __init__(self, engine: Engine, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("PostgresProjectRepository requires a PostgreSQL engine")
        self.engine = engine
        self.workspace_id = workspace_id

    @classmethod
    def from_url(cls, database_url: str) -> "PostgresProjectRepository":
        return cls(create_engine(database_url, pool_pre_ping=True))

    @property
    def persistence_name(self) -> str:
        return "postgresql"

    def _ensure_workspace(self, connection: Any) -> None:
        connection.execute(
            postgres_insert(workspace)
            .values(id=self.workspace_id, name="Default workspace")
            .on_conflict_do_nothing(index_elements=[workspace.c.id])
        )

    def create_project(self, project_id: str, title: str, premise: str) -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._ensure_workspace(connection)
            connection.execute(
                insert(project).values(
                    id=project_id,
                    workspace_id=self.workspace_id,
                    title=title,
                    premise=premise,
                    production_state="PLANNED",
                )
            )
        return self.get_project(project_id) or {}

    def list_projects(self) -> list[dict[str, Any]]:
        statement = (
            select(project)
            .where(project.c.workspace_id == self.workspace_id)
            .order_by(project.c.created_at.desc())
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._project_dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        statement = select(project).where(
            project.c.id == project_id,
            project.c.workspace_id == self.workspace_id,
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return self._project_dict(row) if row else None

    @staticmethod
    def _project_dict(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "premise": row["premise"],
            "production_state": row["production_state"],
            "rough_cut_asset_id": row["rough_cut_asset_id"],
        }

    def set_rendered(self, project_id: str, asset_id: str, media_path: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(asset).values(
                    id=asset_id,
                    workspace_id=self.workspace_id,
                    project_id=project_id,
                    kind="ROUGH_CUT",
                )
            )
            connection.execute(
                insert(asset_version).values(
                    id=asset_id,
                    asset_id=asset_id,
                    state="PUBLISHED",
                    storage_uri=media_path,
                    media_metadata={},
                )
            )
            connection.execute(
                update(project)
                .where(project.c.id == project_id, project.c.workspace_id == self.workspace_id)
                .values(production_state="ROUGH_CUT_READY", rough_cut_asset_id=asset_id)
            )

    def get_asset_path(self, asset_id: str) -> Path | None:
        statement = (
            select(asset_version.c.storage_uri)
            .select_from(asset_version.join(asset, asset_version.c.asset_id == asset.c.id))
            .where(asset_version.c.id == asset_id, asset.c.workspace_id == self.workspace_id)
        )
        with self.engine.connect() as connection:
            storage_uri = connection.execute(statement).scalar_one_or_none()
        return Path(storage_uri) if storage_uri and "://" not in storage_uri else None


def create_default_repository() -> ProjectRepository:
    if DATABASE_URL:
        if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("DRAMA_DATABASE_URL must be a PostgreSQL URL")
        return PostgresProjectRepository.from_url(DATABASE_URL)
    if ENVIRONMENT in POSTGRES_REQUIRED_ENVIRONMENTS:
        raise RuntimeError(f"DRAMA_DATABASE_URL is required when DRAMA_ENV={ENVIRONMENT}")
    return SqliteProjectRepository(DATABASE_PATH)
