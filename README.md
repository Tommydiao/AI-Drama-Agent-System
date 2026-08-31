# AI Drama Agent System — Mock MVP

## Native Windows development (Local Mock MVP)

The one-command launcher starts FastAPI and Next.js, waits for the API health check, and opens the product in your browser:

```powershell
.\scripts\start-local.ps1
```

On a fresh checkout, install the API environment and web dependencies once:

```powershell
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -e "apps/api[dev]"

cd apps/web
pnpm install
```

Run the automated browser journey against the running app with `pnpm e2e` from `apps/web`. Local Mock development uses SQLite behind `ProjectRepository`; the production PostgreSQL adapter and migrations are described below and require a real PostgreSQL integration environment for their Gate.

## PostgreSQL integration

Staging, Beta, and production require PostgreSQL and never fall back to SQLite. Set `DRAMA_DATABASE_URL`, apply the canonical Alembic migration, and start the API with `DRAMA_ENV` set to the target environment:

```powershell
$env:DRAMA_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:5432/ai_drama'
$env:DRAMA_ENV = 'staging'
apps/api/.venv/Scripts/python.exe -m alembic -c apps/api/alembic.ini upgrade head
```

Run the PostgreSQL migration and concurrency Gate against a disposable integration database:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:5432/ai_drama_test'
.\scripts\test-postgres.ps1
```

Local Mock development continues to use SQLite when `DRAMA_DATABASE_URL` is unset. PostgreSQL schema changes must go through Alembic; `infra/postgres/init.sql` only prepares separate local Temporal databases.
