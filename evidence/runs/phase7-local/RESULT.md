# Phase 7 acceptance evidence

Date: 2026-08-30 (Asia/Shanghai)

## Live browser run

- Next.js home loaded with the Chinese title/premise form.
- Form submission reached FastAPI and rendered the full Mock flow.
- Post-render DOM contained one playable `<video>` and `ROUGH_CUT_READY`.
- Screenshot: `final-browser.png`.

## Final media probe

The browser run produced a 60.021354-second MP4. The saved `final-ffprobe.json` reports:

- video: H.264, 720×1280, 30/1 fps
- audio: AAC, 48 kHz
- file size: 678,313 bytes

## Gate status

Safe Mock implementation and local acceptance tests pass. Final MVP gate is BLOCKED because the mandatory Phase-5 supported long-lived Temporal recovery/versioning gate could not be executed: no Temporal SDK/CLI/server is installed or reachable, and the required PostgreSQL integration environment is not available on this host.
