# AI Short Drama Agent — Mock MVP Build Report

## Status

MOCK_MVP_GATE = BLOCKED

The safe native-Windows Mock MVP path is implemented and locally verified. The final gate remains blocked by the approved Phase-5 infrastructure gates; no alternate workflow engine or paid provider was introduced.

## Built capabilities

- Chinese one-sentence story input with default benchmark `门外的人`.
- FastAPI domain boundary and local Next.js App Router UI.
- Database-agnostic `ProjectRepository` with the Product Owner-approved temporary Phase-1 SQLite implementation.
- Deterministic 15-shot × 4-second Mock production, real MP4 clips, SRT subtitles, AAC audio, and FFmpeg concat output.
- Final 60-second vertical rough cut playable in the browser.
- Canonical Shot/ShotVersion and Operation/BudgetReservation semantic invariants.
- Single-shot regeneration, candidate replacement, dialogue impact-plan modeling, dependency scope, asset reuse, timeline versioning, pause/resume, two-repair human issue escalation, operation idempotency, submission reconciliation, concurrent budget protection, and mock cost/evidence manifests.
- Artifact, cost, evidence, pause, resume, regeneration, replacement, and impact-plan API routes.
- UI artifact summary, QC/timeline display, pause/resume controls, and evidence action.

## Architecture used

Next.js → FastAPI → repository boundary → deterministic Mock service → local filesystem `StoragePort` → FFmpeg/ffprobe. PostgreSQL remains the target Phase-2/5 domain store. Temporal remains behind the planned `OrchestrationPort` and was not replaced.

## Phases and tests

- Phase 0: native Node/pnpm, Python 3.12 virtual environment, FFmpeg/ffprobe, SQLite, documented commands; Docker/Compose deferred as approved.
- Phase 1: live browser-to-MP4 vertical slice.
- Phase 2: domain state and authorization invariants.
- Phase 3: full 60-second deterministic Mock render.
- Phase 4: editing/invalidation/reuse services and API routes.
- Phase 5: safe in-process reliability/evidence behaviors; infrastructure gate not passed.
- Phase 6: usable production overview UI.
- Phase 7: final live browser/media evidence.

Automated API/domain suite: **16 passed**. Next.js production build: **passed**. Browser verification: **passed**. Final ffprobe evidence: [final-ffprobe.json](evidence/runs/phase7-local/final-ffprobe.json).

## Acceptance matrix

| Requirement | Result | Evidence |
| --- | --- | --- |
| Full Mock story → rough-cut MP4 | PASS | `test_full_mock_story_to_rough_cut_mp4`, final browser run |
| 720×1280 / 30 fps | PASS | `final-ffprobe.json` |
| Single Shot regeneration | PASS | `test_regenerate_one_shot_only` |
| Shot candidate replacement / TimelineVersion | PASS | `test_replace_shot_creates_timeline_version` |
| Minimal dialogue invalidation | PASS | `test_dialogue_edit_impact_is_minimal` |
| Maximum two repairs then human issue | PASS | `test_repair_stops_after_two_and_waits_human` |
| Concurrent budget protection | PASS | `test_concurrent_reservation_allows_only_one` |
| Restart/idempotency behavior | PASS (Mock service) | `test_worker_restart_reconciles_without_duplicate_operation` |
| Pause blocks new generation | PASS | `test_pause_blocks_new_generation_and_reconciles_inflight` |
| Unchanged asset reuse | PASS | `test_unchanged_assets_are_reused` |
| `SUBMISSION_UNKNOWN` reconciliation | PASS | `test_submission_unknown_reconciles_same_operation` |
| Evidence and Mock cost ledger | PASS | `test_evidence_manifest_and_mock_cost_ledger_complete` |
| PostgreSQL integration | BLOCKED | No safe local PostgreSQL server available |
| Supported long-lived Temporal recovery/versioning | BLOCKED | No Temporal SDK/CLI/server; port 7233 unavailable |

## Evidence and media

- [Phase 0 environment](evidence/phase0-environment.md)
- [Phase 1 result](evidence/runs/phase1-local/RESULT.md)
- [Phase 7 result](evidence/runs/phase7-local/RESULT.md)
- [Final browser screenshot](evidence/runs/phase7-local/final-browser.png)
- [Final ffprobe JSON](evidence/runs/phase7-local/final-ffprobe.json)
- Benchmark MP4: `data/storage/c35fa84f-686c-4952-a3a8-3d6a7468b188/rough-cut.mp4` (local generated artifact)

## Known limitations and risks

- Phase-1 runtime persistence is SQLite; production persistence and budget-concurrency claims must be re-run against PostgreSQL in Phase 2/5.
- Mock media uses deterministic color/sine assets; no paid provider credentials or real provider calls are present.
- Temporal cross-process recovery/versioning is not claimed because the supported long-lived deployment gate was not available.
- The current local service process stores advanced Mock editing state in memory; the PostgreSQL adapter must persist it before production use.

## Next recommended step

Provide a safely available PostgreSQL instance and a supported long-lived Temporal deployment, then rerun the Phase-5 integration/recovery gate without changing the approved domain contracts or introducing another orchestration engine.
