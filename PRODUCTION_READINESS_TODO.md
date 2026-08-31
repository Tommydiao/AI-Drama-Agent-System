# Production Readiness TODO

These items are intentionally deferred and do not block the Local Mock MVP.

- Run the implemented Alembic/PostgreSQL repository and migration suite against an available PostgreSQL integration database.
- Execute `scripts/test-postgres.ps1` to prove the implemented row-locking behavior for concurrent `BudgetReservation` authorization; this environment currently has no Docker or PostgreSQL service.
- Deploy a supported long-lived Temporal service behind `OrchestrationPort`.
- Re-run worker handoff, restart recovery, deterministic retry, and workflow-versioning evidence against Temporal.
- Harden Docker/WSL Compose reproducibility for team onboarding.
- Add production authentication, authorization, retention, object storage, observability, and deployment controls before any external release.

No paid-provider credentials, private user data, or production infrastructure are required for the Local Mock MVP.
