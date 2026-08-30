# AI Drama Agent System — Mock MVP

## Native Windows development (Phase 1)

```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn app.main:app --reload

cd ..\web
pnpm install
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
pnpm dev
```

Run API tests with `apps/api/.venv/Scripts/python -m pytest`. The Phase-1 repository implementation is temporary SQLite; the domain API only depends on `ProjectRepository`. Docker/Compose and PostgreSQL are deferred to the approved hardening and Phase-2 work respectively.
