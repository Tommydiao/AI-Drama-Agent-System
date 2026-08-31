"""Canonical SQLAlchemy schema used by PostgreSQL and Alembic."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


workspace = Table(
    "workspace",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

actor = Table(
    "actor",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("external_subject", String(255), nullable=False),
    Column("role", String(32), nullable=False),
    UniqueConstraint("workspace_id", "external_subject"),
)

project = Table(
    "project",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", ForeignKey("workspace.id", ondelete="RESTRICT"), nullable=False, index=True),
    Column("title", String(120), nullable=False),
    Column("premise", Text, nullable=False),
    Column("production_state", String(32), nullable=False, default="PLANNED"),
    Column("rough_cut_asset_id", String(36)),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

shot = Table(
    "shot",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("production_state", String(32), nullable=False, default="PLANNED"),
    Column("creative_repair_count", Integer, nullable=False, default=0),
    UniqueConstraint("project_id", "position"),
    CheckConstraint("creative_repair_count >= 0 AND creative_repair_count <= 2", name="repair_count_range"),
)

shot_version = Table(
    "shot_version",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("shot_id", ForeignKey("shot.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("version_status", String(32), nullable=False, default="DRAFT"),
    Column("spec_hash", String(64), nullable=False),
    Column("spec", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

asset = Table(
    "asset",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", ForeignKey("workspace.id", ondelete="RESTRICT"), nullable=False, index=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("kind", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

asset_version = Table(
    "asset_version",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("asset_id", ForeignKey("asset.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("state", String(32), nullable=False, default="PUBLISHED"),
    Column("storage_uri", Text, nullable=False),
    Column("sha256", String(64)),
    Column("media_metadata", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

operation = Table(
    "operation",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("idempotency_key", String(255), nullable=False),
    Column("capability", String(32), nullable=False),
    Column("state", String(32), nullable=False, default="PLANNED"),
    Column("is_paid", Boolean, nullable=False, default=False),
    Column("no_charge_policy_fact", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    UniqueConstraint("project_id", "idempotency_key"),
)

provider_attempt = Table(
    "provider_attempt",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("operation_id", ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("provider", String(64), nullable=False),
    Column("model_route", String(128), nullable=False),
    Column("state", String(32), nullable=False),
    Column("client_reference", String(255), nullable=False),
    Column("external_job_id", String(255)),
    Column("raw_response_hash", String(64)),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    UniqueConstraint("provider", "client_reference"),
)

job = Table(
    "job",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("operation_id", ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("state", String(32), nullable=False),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("available_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

issue = Table(
    "issue",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("shot_id", ForeignKey("shot.id", ondelete="CASCADE")),
    Column("kind", String(64), nullable=False),
    Column("state", String(32), nullable=False, default="OPEN"),
    Column("details", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

timeline = Table(
    "timeline",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, unique=True),
)

timeline_version = Table(
    "timeline_version",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("timeline_id", ForeignKey("timeline.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("version_number", Integer, nullable=False),
    Column("clips", JSON, nullable=False, default=list),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    UniqueConstraint("timeline_id", "version_number"),
)

budget = Table(
    "budget",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("currency", String(3), nullable=False),
    Column("approved_minor", BigInteger, nullable=False),
    Column("state", String(32), nullable=False, default="ACTIVE"),
    UniqueConstraint("project_id", "currency"),
    CheckConstraint("approved_minor >= 0", name="approved_nonnegative"),
)

budget_reservation = Table(
    "budget_reservation",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("budget_id", ForeignKey("budget.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("operation_id", ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("state", String(32), nullable=False),
    Column("amount_minor", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    CheckConstraint("amount_minor > 0", name="amount_positive"),
)

cost_event = Table(
    "cost_event",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("budget_id", ForeignKey("budget.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("operation_id", ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("provider_attempt_id", ForeignKey("provider_attempt.id", ondelete="SET NULL")),
    Column("kind", String(32), nullable=False),
    Column("amount_minor", BigInteger, nullable=False),
    Column("is_mock", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

evidence_record = Table(
    "evidence_record",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("kind", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

event_outbox = Table(
    "event_outbox",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("aggregate_type", String(64), nullable=False),
    Column("aggregate_id", String(36), nullable=False, index=True),
    Column("event_type", String(128), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    Column("published_at", DateTime(timezone=True)),
)

callback_inbox = Table(
    "callback_inbox",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("provider", String(64), nullable=False),
    Column("provider_event_id", String(255), nullable=False),
    Column("body_sha256", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False, default=utcnow),
    Column("processed_at", DateTime(timezone=True)),
    UniqueConstraint("provider", "provider_event_id"),
)
