# Phase 0 environment evidence

Date checked: 2026-08-29 (Asia/Shanghai)

- Node.js 24.14.0, pnpm 11.19.0, and Python 3.12.10 are available.
- FFmpeg 9.0.1 and ffprobe were installed through Chocolatey and are available on `PATH`.
- Docker and Docker Compose are not installed; WSL is not installed on this Windows 10 Pro host.
- Product Owner approved a native Windows local-development path. Docker/Compose is deferred to reproducibility hardening and is not a Phase 0 or Phase 1 blocker.
- No native PostgreSQL tools or installation are present. Installing a service-level PostgreSQL distribution would be machine configuration, so the approved Phase-1 SQLite fallback will be used only behind database-agnostic repository interfaces. PostgreSQL remains mandatory in Phase 2.

Result: approved native path selected: local Node/pnpm, Python virtual environment, FFmpeg/ffprobe, local filesystem storage, and temporary SQLite persistence. Docker/Compose remains TODO for reproducibility hardening.
