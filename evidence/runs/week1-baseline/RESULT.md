# Week 1 Trusted Baseline Evidence

Date: 2026-08-31

## Scope

- Review the complete Local Mock MVP branch against `main`.
- Preserve `EXPLORE_REPORT.md` byte-for-byte relative to `main`.
- Remove the Starlette test-client deprecation warning.
- Re-run API/domain tests, the web production build, browser E2E, and final-media probing.

## Repository review

- Source branch: `codex/p0-technical-spikes`.
- Baseline branch: `main` at `758902c` before integration.
- `EXPLORE_REPORT.md`: unchanged between `main` and the source branch.
- Generated Python `*.egg-info` metadata is ignored and no longer source-controlled.
- Starlette 1.6 test support now uses the declared `httpx2>=2.12,<3` development dependency.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| API/domain regression | `apps/api/.venv/Scripts/python.exe -m pytest -q` | PASS: 16 tests |
| Web production build | `pnpm build` in `apps/web` | PASS |
| Browser journey | `pnpm e2e` in `apps/web` | PASS: 1 Playwright test |
| Media profile | `ffprobe` on the latest persisted rough cut | PASS |

Verified media profile:

- duration: 60.021354 seconds
- video: H.264, 720x1280, 30 fps
- audio: AAC, 48 kHz

## Gate

`WEEK_01_TRUSTED_BASELINE = PASS`

The baseline is eligible for integration into `main` and tagging as `local-mock-mvp-v1`.
