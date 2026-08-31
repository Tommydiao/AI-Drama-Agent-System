# Production Readiness TODO

These items are intentionally deferred and do not block the Local Mock MVP.

- Run the implemented Alembic/PostgreSQL repository and migration suite against an available PostgreSQL integration database.
- Execute `scripts/test-postgres.ps1` to prove the implemented row-locking behavior for concurrent `BudgetReservation` authorization; this environment currently has no Docker or PostgreSQL service.
- Deploy the implemented Temporal adapter against a private service with persistent PostgreSQL storage, TLS, metrics, backup, and pinned versions.
- Re-run the now-passing worker handoff, restart recovery, deterministic retry, and workflow-versioning suite against that persistent deployment.
- Harden Docker/WSL Compose reproducibility for team onboarding.
- Add production authentication, authorization, retention, object storage, observability, and deployment controls before any external release.

No paid-provider credentials, private user data, or production infrastructure are required for the Local Mock MVP.
