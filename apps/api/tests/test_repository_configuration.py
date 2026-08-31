from pathlib import Path

import pytest

import app.repository as repository_module
from app.repository import PostgresProjectRepository, SqliteProjectRepository


def test_sqlite_repository_identifies_local_persistence(tmp_path: Path):
    repository = SqliteProjectRepository(tmp_path / "local.sqlite3")
    assert repository.persistence_name == "sqlite-local"


def test_postgres_repository_rejects_non_postgres_engine():
    from sqlalchemy import create_engine

    with pytest.raises(ValueError, match="PostgreSQL"):
        PostgresProjectRepository(create_engine("sqlite:///:memory:"))


def test_production_cannot_silently_fall_back_to_sqlite(monkeypatch):
    monkeypatch.setattr(repository_module, "ENVIRONMENT", "production")
    monkeypatch.setattr(repository_module, "DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="DRAMA_DATABASE_URL is required"):
        repository_module.create_default_repository()


def test_database_url_must_be_postgresql(monkeypatch):
    monkeypatch.setattr(repository_module, "ENVIRONMENT", "local")
    monkeypatch.setattr(repository_module, "DATABASE_URL", "sqlite:///forbidden.sqlite3")
    with pytest.raises(RuntimeError, match="must be a PostgreSQL URL"):
        repository_module.create_default_repository()
