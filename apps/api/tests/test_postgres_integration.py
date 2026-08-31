from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, insert

from app.db import (
    asset,
    asset_version,
    budget,
    budget_reservation,
    callback_inbox,
    metadata,
    operation,
    project,
    workspace,
)
from app.ledger import PostgresLedger
from app.repository import PostgresProjectRepository


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def test_postgres_project_repository_round_trip(tmp_path):
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    metadata.create_all(engine)
    workspace_id = str(uuid4())
    repository = PostgresProjectRepository(engine, workspace_id=workspace_id)
    project_id = str(uuid4())
    asset_id = str(uuid4())
    media_path = str(tmp_path / "rough-cut.mp4")
    try:
        created = repository.create_project(project_id, "PostgreSQL", "Repository round trip")
        assert created["production_state"] == "PLANNED"
        repository.set_rendered(project_id, asset_id, media_path)
        loaded = repository.get_project(project_id)
        assert loaded is not None
        assert loaded["rough_cut_asset_id"] == asset_id
        assert repository.get_asset_path(asset_id) == tmp_path / "rough-cut.mp4"
    finally:
        with engine.begin() as connection:
            connection.execute(delete(asset_version).where(asset_version.c.asset_id == asset_id))
            connection.execute(delete(asset).where(asset.c.id == asset_id))
            connection.execute(delete(project).where(project.c.id == project_id))
            connection.execute(delete(workspace).where(workspace.c.id == workspace_id))
        engine.dispose()


def test_postgres_concurrent_reservation_allows_only_one():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    metadata.create_all(engine)
    suffix = str(uuid4())
    workspace_id = str(uuid4())
    project_id = str(uuid4())
    budget_id = str(uuid4())
    operation_ids = [str(uuid4()), str(uuid4())]
    try:
        with engine.begin() as connection:
            connection.execute(insert(workspace).values(id=workspace_id, name=f"test-{suffix}"))
            connection.execute(
                insert(project).values(
                    id=project_id,
                    workspace_id=workspace_id,
                    title="Concurrency",
                    premise="Budget locking",
                    production_state="PLANNED",
                )
            )
            connection.execute(
                insert(budget).values(
                    id=budget_id,
                    project_id=project_id,
                    currency="CNY",
                    approved_minor=100,
                    state="ACTIVE",
                )
            )
            for operation_id in operation_ids:
                connection.execute(
                    insert(operation).values(
                        id=operation_id,
                        project_id=project_id,
                        idempotency_key=operation_id,
                        capability="VIDEO",
                        state="PLANNED",
                        is_paid=True,
                    )
                )
        ledger = PostgresLedger(engine)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda pair: ledger.reserve_budget(
                        reservation_id=str(uuid4()),
                        budget_id=budget_id,
                        operation_id=pair[0],
                        amount_minor=pair[1],
                    ),
                    zip(operation_ids, [60, 60]),
                )
            )
        assert sorted(results) == [False, True]
    finally:
        with engine.begin() as connection:
            connection.execute(delete(budget_reservation).where(budget_reservation.c.budget_id == budget_id))
            connection.execute(delete(operation).where(operation.c.project_id == project_id))
            connection.execute(delete(budget).where(budget.c.project_id == project_id))
            connection.execute(delete(project).where(project.c.id == project_id))
            connection.execute(delete(workspace).where(workspace.c.id == workspace_id))
        engine.dispose()


def test_postgres_callback_inbox_is_idempotent():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    metadata.create_all(engine)
    ledger = PostgresLedger(engine)
    event_id = str(uuid4())
    try:
        assert ledger.accept_callback(
            inbox_id=str(uuid4()),
            provider="test-provider",
            provider_event_id=event_id,
            body_sha256="0" * 64,
            payload={"state": "succeeded"},
        )
        assert not ledger.accept_callback(
            inbox_id=str(uuid4()),
            provider="test-provider",
            provider_event_id=event_id,
            body_sha256="0" * 64,
            payload={"state": "succeeded"},
        )
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(callback_inbox).where(
                    callback_inbox.c.provider == "test-provider",
                    callback_inbox.c.provider_event_id == event_id,
                )
            )
        engine.dispose()
