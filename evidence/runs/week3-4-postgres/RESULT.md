# Week 3–4 PostgreSQL Implementation Evidence

Date: 2026-08-31

## Delivered

- Canonical SQLAlchemy metadata for workspace, actor, project, shot/version, asset/version, operation/provider attempt/job, issue, timeline/version, budget/reservation/cost, Evidence, EventOutbox, and CallbackInbox.
- Alembic revision `20260831_0001` as the only application-schema initializer.
- `PostgresProjectRepository`; staging, Beta, and production reject a missing or non-PostgreSQL `DRAMA_DATABASE_URL`.
- Atomic `PostgresLedger.reserve_budget()` with a `FOR UPDATE` lock on the owning Budget.
- Idempotent CallbackInbox insert on `(provider, provider_event_id)`.
- PostgreSQL project round-trip, concurrent 60+60 against 100, and duplicate callback integration tests.
- `scripts/test-postgres.ps1` for applying migrations and running the live Gate.

## Verification in this environment

| Check | Result |
| --- | --- |
| Python/API/domain suite | PASS: 20 tests |
| PostgreSQL-only integration tests | NOT RUN: 3 tests skipped because `TEST_DATABASE_URL` is unavailable |
| Alembic PostgreSQL offline SQL generation | PASS |
| Python bytecode compilation | PASS |
| Next.js production build | PASS |

Docker, a local PostgreSQL service, `psql`, and PostgreSQL credentials are unavailable on this machine. No machine-level database installation was attempted.

## Remaining live Gate

Provide a disposable PostgreSQL database and run:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:5432/ai_drama_test'
.\scripts\test-postgres.ps1
```

The Gate passes only when Alembic applies successfully and all three PostgreSQL integration tests pass, including exactly one successful reservation for two concurrent 60-unit requests against a 100-unit budget.

`WEEK_03_04_POSTGRES_IMPLEMENTATION = PASS`

`WEEK_04_POSTGRES_LIVE_GATE = WAITING_FOR_POSTGRESQL`
