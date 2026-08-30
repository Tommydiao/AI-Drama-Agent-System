# AI Short Drama Agent — Local Mock MVP Build Report

## Final gate

LOCAL_MOCK_MVP_GATE = PASS

The Product Owner can launch the native Windows app with one command and complete the Mock flow from the browser without manually calling FastAPI, running FFmpeg, editing SQLite, or using developer tools.

## Launch and architecture

Run `powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1` from the repository root. The launcher starts FastAPI and Next.js, waits for `/health`, and opens `http://127.0.0.1:3000`.

The implemented local architecture is:

`Next.js App Router → FastAPI domain boundary → database-agnostic ProjectRepository (SQLite local adapter) → MockProductionService → local filesystem StoragePort → FFmpeg/ffprobe`.

The approved architecture boundaries remain intact. PostgreSQL, Temporal, Docker/WSL, and production infrastructure are recorded in [PRODUCTION_READINESS_TODO.md](PRODUCTION_READINESS_TODO.md), not silently substituted into the local MVP.

## User-visible capabilities

- Enter a one-sentence Chinese story idea and start automatic production.
- See an explicit production progress bar and recover a persisted project after browser refresh.
- Inspect ProductionBrief, StoryBible, Screenplay, 15-shot storyboard, Shot Graph summary, Timeline version, and QC status.
- Play a real approximately 60-second 720×1280 vertical MP4 with H.264 video, AAC audio, and generated SRT subtitles.
- Regenerate one shot, replace its candidate, and see the updated timeline version without touching unrelated shots.
- Edit one dialogue line through an impact plan limited to the affected shot/audio/subtitle descendants.
- Run the two-repair limit and inspect the resulting human Issue.
- Pause/resume production and inspect Mock cost and evidence panels.
- Run a second arbitrary story fixture (`雨夜来信`) through the same browser flow.

## Verification

- API/domain/media regression: **16 passed** with `apps/api/.venv/Scripts/python.exe -m pytest -q`.
- Next.js production build: **passed** with `pnpm build`.
- Browser E2E: **1 passed** with `pnpm e2e` (25.7 seconds) using [local-mvp.spec.ts](apps/web/e2e/local-mvp.spec.ts).
- Fresh-browser restore: workspace and one video element restored from persisted project data.
- Latest benchmark fixture `夜航灯` MP4: `data/storage/6828174a-cc05-4176-97fa-8a2ccef7ce58/rough-cut.mp4`.
- Latest ffprobe: duration `60.021354` seconds, H.264 `720×1280` at `30/1`, AAC `48000` Hz, size `678313` bytes.

## Acceptance matrix

| Requirement | Result | Evidence |
| --- | --- | --- |
| Create project and enter one-sentence idea | PASS | Playwright E2E and `01-created-and-playing.png` |
| Full story → playable MP4 | PASS | `test_full_mock_story_to_rough_cut_mp4`, latest MP4 |
| 720×1280 / 30 fps / audio | PASS | `final-ffprobe.json`, latest ffprobe |
| Generated structure and 12–24 shots | PASS | UI `分镜 (15)`, artifacts endpoint, E2E |
| Single-shot regeneration | PASS | `test_regenerate_one_shot_only`, E2E |
| Candidate replacement / TimelineVersion | PASS | `test_replace_shot_creates_timeline_version`, `02-shot-replaced.png` |
| Minimal dialogue invalidation | PASS | `test_dialogue_edit_impact_is_minimal`, `03-dialogue-repair.png` |
| Two repairs then human Issue | PASS | `test_repair_stops_after_two_and_waits_human`, E2E |
| Pause/resume | PASS | API/UI controls and E2E route coverage |
| Mock cost inspection | PASS | Cost panel, `test_evidence_manifest_and_mock_cost_ledger_complete` |
| Evidence inspection | PASS | Evidence panel and `04-evidence-issue.png` |
| Second arbitrary story | PASS | `07-second-story.png`, `09-second-story-full.png`, persisted restore |
| Local launch reliability | PASS | `scripts/start-local.ps1` health-gated launcher |

## Evidence locations

- [Local flow screenshots](evidence/runs/local-mvp/)
- [Phase 1 evidence](evidence/runs/phase1-local/)
- [Latest full-page second-story screenshot](evidence/runs/local-mvp/09-second-story-full.png)
- [Final browser screenshot](evidence/runs/phase7-local/final-browser.png)
- [Final ffprobe JSON](evidence/runs/phase7-local/final-ffprobe.json)
- [Phase 0 environment record](evidence/phase0-environment.md)

## Known limitations

- SQLite and in-process Mock orchestration are local-MVP choices; they are not production persistence or distributed-worker evidence.
- Media is deterministic Mock color/sine content; no paid AI provider is connected.
- The current UI exposes the approved local Mock surface, not production authentication, collaboration, billing, or deployment controls.

## Next recommended step

Complete the items in `PRODUCTION_READINESS_TODO.md` in a supported environment, starting with PostgreSQL repository integration and then the long-lived Temporal recovery/versioning gate.
