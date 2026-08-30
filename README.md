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

Run the automated browser journey against the running app with `pnpm e2e` from `apps/web`. The Phase-1 repository implementation is temporary SQLite; the domain API only depends on `ProjectRepository`. Docker/Compose and PostgreSQL are deferred to the approved hardening and Phase-2 work respectively.
