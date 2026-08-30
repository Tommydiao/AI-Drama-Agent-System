# IMPLEMENTATION_PLAN.md — Mock MVP Delivery Plan

## Delivery mandate

Build the approved Mock MVP without real paid AI providers. The product is a Chinese, vertical short-drama creator experience: a user enters a story premise and receives a playable, evidence-backed 720×1280, 30 fps MP4. The normal full-Mock target is a deterministic 60-second, 15-shot (4 seconds each) project.

The authority order is `INTENT.md`, `02_DECISIONS.md`, the approved architecture/data-contract/state-machine documents, this plan, then implementation. PostgreSQL is domain truth; orchestration is not domain truth. The MVP does not introduce a ProductionRun entity.

## Technology and boundaries

| Boundary | MVP choice |
| --- | --- |
| Web | Next.js App Router, TypeScript, pnpm |
| API/domain boundary | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2, Alembic |
| Domain persistence | PostgreSQL |
| Storage | `StoragePort`; temporary validation/hash then immutable publication |
| Media | FFmpeg/ffprobe, H.264/yuv420p video and AAC/48 kHz audio, Chinese-capable font |
| Orchestration | `OrchestrationPort`; inline Mock adapter in early phases, Temporal only at Phase 5 |
| Verification | pytest/API tests, Playwright browser tests, ffprobe evidence |

FastAPI is the sole domain API. The browser never receives server filesystem paths. Mock costs are explicitly marked `is_mock=true`. Stable operation IDs and idempotency keys are mandatory; an operation in `SUBMISSION_UNKNOWN` is reconciled, never blindly resubmitted.

## API shape

The first vertical slice exposes these domain-oriented endpoints, expanded only as later phases require:

- `POST /projects`; `GET /projects/{project_id}`
- `POST /projects/{project_id}/commands/start`
- `GET /assets/{asset_version_id}/content`
- `POST /shots/{shot_id}/commands/regenerate`
- `POST /timelines/{timeline_id}/commands/replace-shot`
- `POST /projects/{project_id}/impact-plans/dialogue-edit`
- `POST /impact-plans/{impact_plan_id}/commands/apply`
- project pause, resume, cancel, and event-read endpoints

## Phase sequence and exit criteria

### Phase 0 — Local development environment

Scaffold `apps/web`, `apps/api`, and `infra/compose.yaml`; pin dependencies; configure media tooling, optional Temporal services, migrations, linting, tests, and OpenAPI capture. Prove database/API connectivity, web startup, and FFmpeg availability. Docker Compose is a later reproducibility-hardening step, not a Phase 0 or Phase 1 invariant. Exit: Next.js, FastAPI, FFmpeg/ffprobe, a usable development database, and tests all run locally with documented commands.

### Phase 1 — Three-shot playable vertical slice

Implement browser → FastAPI → persistence → inline Mock orchestration → real media. Persist the smallest canonical subset; generate deterministic story fixture data, three real vertical clips, WAV/AAC, SRT, a timeline, and a final MP4. Provide a minimal new-project/playback UI. Test creation/start/polling, media profile, and browser playback. This phase may be shorter than 60 seconds; it deliberately excludes broad editing and reliability work. If PostgreSQL cannot be safely installed without machine-level setup, use SQLite only through database-agnostic repository interfaces for this phase; Phase 2 replaces it with PostgreSQL and retains mandatory PostgreSQL integration tests.

### Phase 2 — Canonical domain and persistence

Implement canonical aggregates, version/state semantics, operations/jobs/reviews/issues, money/evidence, inbox/outbox, typed dependency graph, and storage metadata. Preserve the approved separation of stable `Shot.production_state` and `ShotVersion.version_status`; only QC-driven creative repair increments the stable Shot repair count. Add migrations and exhaustive state/invariant tests. Phase 1 remains green.

### Phase 3 — Full Mock production

Implement a deterministic `TemplateStoryPlanner` for 15×4-second shots and full structured artifacts. Add Mock image/video/TTS/music/QC capabilities behind ports; write real generated assets and render a full 60-second result. Test full story-to-MP4, profile, graph correctness, and independent-shot behavior.

### Phase 4 — Editing, invalidation, and asset reuse

Implement single-shot regeneration as a new candidate operation on the same ShotVersion where the spec is unchanged; spec-changing inputs create a new ShotVersion. Implement timeline replacement, minimal dialogue-edit impact plans, full rerendering, and unchanged-asset reuse. Test regeneration scope, timeline-version replacement, minimal invalidation, and reuse.

### Phase 5 — Local reliability, budget, recovery, and evidence

Implement local SQLite-backed Mock budget/idempotency semantics, `SUBMISSION_UNKNOWN` reconciliation, callback inbox/outbox shape, creative repair cap, pause/cancel, mock cost ledger, and evidence manifests. Operations become `AUTHORIZED` independently from reservations: paid authorization requires an ACTIVE reservation; provably free authorization requires a persisted no-charge policy fact. PostgreSQL concurrency and supported long-lived Temporal recovery/versioning are production-readiness work, recorded in `PRODUCTION_READINESS_TODO.md`; they do not block the Local Mock MVP.

### Phase 6 — Product UI

Build projects/new project, overview, storyboard, issue/review, rough-cut, cost, and evidence views. Use SSE with polling fallback. Keep state visible and action-oriented; no broad SaaS/team surface.

### Phase 7 — End-to-end acceptance

Run clean, deterministic end-to-end scenarios including the benchmark story `门外的人`; export artifacts and evidence under `evidence/runs/<run_id>`. Complete human review of results and produce `MVP_BUILD_REPORT.md`.

## Mandatory acceptance matrix

| Acceptance row | Required automated evidence |
| --- | --- |
| Full Mock story to rough-cut MP4 | `test_full_mock_story_to_rough_cut_mp4` |
| 720×1280 / 30 fps | `test_final_media_profile` |
| One-shot regeneration scope | `test_regenerate_one_shot_only` |
| Timeline replacement versioning | `test_replace_shot_creates_timeline_version` |
| Minimal dialogue invalidation | `test_dialogue_edit_impact_is_minimal` |
| At most two repairs, then human wait | `test_repair_stops_after_two_and_waits_human` |
| Concurrent reservation protection | `test_concurrent_reservation_allows_only_one` |
| Restart recovery without duplicate operation | `test_worker_restart_reconciles_without_duplicate_operation` |
| Pause behavior | `test_pause_blocks_new_generation_and_reconciles_inflight` |
| Unchanged asset reuse | `test_unchanged_assets_are_reused` |
| Unknown submission reconciliation | `test_submission_unknown_reconciles_same_operation` |
| Complete evidence and mock cost ledger | `test_evidence_manifest_and_mock_cost_ledger_complete` |

## Implementation notes

- Initial delivery path is Phase 0 → Phase 1. The complete path is Phase 0 through Phase 7.
- The Local Mock MVP uses the current local orchestration adapter. Temporal remains behind `OrchestrationPort` and is deferred to the production-readiness gate; no alternate production workflow engine is introduced.
- Evidence lives under `evidence/runs/<run_id>` and includes test output, media probes, hashes, costs, and browser screenshots.
- Docker/Compose is deferred to reproducibility hardening. The approved native Windows path uses local Node/pnpm, a Python virtual environment, FFmpeg/ffprobe, local filesystem `StoragePort`, no Temporal, and no paid providers. PostgreSQL remains the target domain store; Phase 1 may use the narrowly approved SQLite repository fallback.

IMPLEMENTATION_PLAN_GATE = APPROVED
