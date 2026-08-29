# P0 Technical Spike Evidence

Scope: disposable P0 experiments only. No product feature, production architecture, UI, or paid AI-provider integration was created.

## SPIKE-01 — Temporal durability + pause/resume

- Hypothesis: a persisted operation ledger plus cooperative pause can survive a worker restart without a duplicate paid operation.
- Minimal experiment: three mock shots; record provider acceptance for shot 2, simulate a crash after acceptance, replace the worker, pause before shot 3, then resume.
- Commands/tests executed: python spikes/p0_harness.py using temporalio 1.32.0 and Temporal's local test server.
- Result: the activity ledger proved one acceptance and one reconciliation for shot 2, but the full worker-handoff plus pause/resume run stalled on sticky workflow-task transfer.
- Status: FAIL
- Evidence path: evidence/spikes/spike_01.json and evidence/spikes/temporal_operations.sqlite.
- Architecture consequence: do not approve Temporal pause/restart semantics yet. Re-run this fixture with independently launched worker processes and explicit task-queue ownership before Architecture.

## SPIKE-02 — Temporal workflow version evolution

- Hypothesis: workflow.patched can preserve an in-flight v1 workflow path while a new run takes a v2 path.
- Minimal experiment: hold v1 at a signal wait, replace its worker with v2, release the old run, then run a fresh v2 workflow.
- Commands/tests executed: versioned workflow definitions were prepared in spikes/temporal_workflows.py; the integrated harness was started with python spikes/p0_harness.py.
- Result: not completed, because SPIKE-01's worker handoff did not complete safely enough to validate replay/versioning.
- Status: FAIL
- Evidence path: evidence/spikes/spike_02.json and spikes/temporal_workflows.py.
- Architecture consequence: retain the versioning requirement, but do not choose a Temporal patching convention until the separate-process replay experiment passes.

## SPIKE-03 — Provider unknown submission / idempotency

- Hypothesis: a stable operation ID, SUBMISSION_UNKNOWN, and provider lookup prevent a second paid job after response loss.
- Minimal experiment: mock provider creates one job then raises a simulated timeout; retry reconciles by operation ID.
- Commands/tests executed: provider_unknown_submission() from spikes/p0_harness.py.
- Result: one provider job, one operation and one cost event; retry reconciled the existing job.
- Status: PASS
- Evidence path: evidence/spikes/spike_03.json.
- Architecture consequence: require stable operation IDs, provider client references/lookup and an explicit SUBMISSION_UNKNOWN state; never blind-retry a paid submission.

## SPIKE-04 — Concurrent budget reservation

- Hypothesis: a transactional reservation ledger serializes two concurrent upper-bound checks.
- Minimal experiment: budget 100; two concurrent operations each reserve 60 through SQLite BEGIN IMMEDIATE.
- Commands/tests executed: concurrent_budget_reservation() from spikes/p0_harness.py.
- Result: exactly one reservation succeeded and the other was explicitly budget-blocked.
- Status: PASS
- Evidence path: evidence/spikes/spike_04.json and evidence/spikes/budget_reservations.sqlite.
- Architecture consequence: model budget as an atomic reservation ledger; PostgreSQL implementation must serialize the equivalent check-and-reserve transaction.

## SPIKE-05 — Shot Graph invalidation

- Hypothesis: typed dependency edges produce a minimal, stable impact plan.
- Minimal experiment: five-shot fixture with dialogue, subtitle, TTS, lip-sync, continuity and character-look edges; apply dialogue and look changes separately.
- Commands/tests executed: shot_graph_invalidation() from spikes/p0_harness.py.
- Result: dialogue change invalidated only shot-2 TTS/subtitle/lip-sync/video assets; look change invalidated only the two relevant look-derived paths. Continuity did not over-invalidate.
- Status: PASS
- Evidence path: evidence/spikes/spike_05.json.
- Architecture consequence: keep Timeline separate from the typed dependency graph, and encode invalidation policy per edge type.

## SPIKE-06 — FFmpeg deterministic render

- Hypothesis: fixed local inputs, options and metadata produce repeatable technical output; byte equality is measured rather than promised.
- Minimal experiment: render three 720x1280/30fps clips, WAV and SRT twice; probe both outputs; replace the middle shot and render again.
- Commands/tests executed: ffmpeg_deterministic_render() from spikes/p0_harness.py, using FFmpeg 8.1.1 and ffprobe.
- Result: both initial renders and the replacement render had matching required video/audio metadata and a 3-second duration.
- Status: PASS
- Evidence path: evidence/spikes/spike_06.json and evidence/spikes/ffmpeg/.
- Architecture consequence: the first Mock can use full deterministic FFmpeg re-render with fixed command snapshots and ffprobe gates; no incremental segment cache is required.

## Gate

P0_SPIKE_GATE = FAIL

SPIKE-01 and SPIKE-02 require a corrected, separately launched Temporal worker-process experiment. INTENT.md and 02_DECISIONS.md were not changed.

STOP / WAITING FOR PRODUCT OWNER REVIEW
