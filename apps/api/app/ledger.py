"""PostgreSQL transaction boundaries for money and provider callbacks."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from .db import budget, budget_reservation, callback_inbox, operation


RESERVED_STATES = ("ACTIVE", "SETTLING", "SETTLED")


class PostgresLedger:
    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("PostgresLedger requires a PostgreSQL engine")
        self.engine = engine

    def reserve_budget(
        self,
        *,
        reservation_id: str,
        budget_id: str,
        operation_id: str,
        amount_minor: int,
    ) -> bool:
        """Atomically check and reserve under a row lock on the owning Budget."""
        if amount_minor <= 0:
            raise ValueError("amount_minor must be positive")
        with self.engine.begin() as connection:
            budget_row = connection.execute(
                select(budget.c.approved_minor, budget.c.state)
                .where(budget.c.id == budget_id)
                .with_for_update()
            ).one_or_none()
            if budget_row is None:
                raise KeyError(f"Budget not found: {budget_id}")
            if budget_row.state != "ACTIVE":
                return False
            reserved_minor = connection.execute(
                select(func.coalesce(func.sum(budget_reservation.c.amount_minor), 0)).where(
                    budget_reservation.c.budget_id == budget_id,
                    budget_reservation.c.state.in_(RESERVED_STATES),
                )
            ).scalar_one()
            if reserved_minor + amount_minor > budget_row.approved_minor:
                return False
            connection.execute(
                insert(budget_reservation).values(
                    id=reservation_id,
                    budget_id=budget_id,
                    operation_id=operation_id,
                    state="ACTIVE",
                    amount_minor=amount_minor,
                )
            )
            return True

    def accept_callback(
        self,
        *,
        inbox_id: str,
        provider: str,
        provider_event_id: str,
        body_sha256: str,
        payload: dict[str, Any],
    ) -> bool:
        """Persist a provider event once; duplicates are successful no-ops."""
        statement = (
            postgres_insert(callback_inbox)
            .values(
                id=inbox_id,
                provider=provider,
                provider_event_id=provider_event_id,
                body_sha256=body_sha256,
                payload=payload,
            )
            .on_conflict_do_nothing(
                index_elements=[callback_inbox.c.provider, callback_inbox.c.provider_event_id]
            )
            .returning(callback_inbox.c.id)
        )
        with self.engine.begin() as connection:
            return connection.execute(statement).scalar_one_or_none() is not None


def create_budget_and_operation(
    engine: Engine,
    *,
    budget_id: str,
    project_id: str,
    operation_id: str,
    amount_minor: int,
    currency: str = "CNY",
) -> None:
    """Small setup helper used by integration tests and application services."""
    with engine.begin() as connection:
        connection.execute(
            insert(budget).values(
                id=budget_id,
                project_id=project_id,
                currency=currency,
                approved_minor=amount_minor,
                state="ACTIVE",
            )
        )
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
