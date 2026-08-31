# 09_EVALUATION_SPEC.md — Real Generation Evaluation

## 1. Evaluation authority

Evaluation is Evidence for a deterministic application decision. A VLM may diagnose and recommend repairs, but only application services can change state, authorize cost, select an asset, or start a repair.

No release claim may be based on a single best sample. Every report includes all attempted samples, failures, costs, latencies, model versions, prompts, human scores, and repair history.

## 2. Fixed five-story regression set

| Fixture | Required coverage |
| --- | --- |
| `门外的人` | two-person dialogue, doorway continuity, reaction shots |
| `雨夜来信` | rain/night lighting, letter prop, voice-over |
| `夜航灯` | moving light, restrained action, ambient audio |
| `纸飞机` | hand/prop interaction, indoor-to-outdoor continuity |
| `最后一班地铁` | public interior, dialogue, empty establishing shot |

Each fixture is 60–90 seconds, 12–24 shots, at most two main characters and one or two locations. The canonical run targets 15 four-second shots and includes dialogue, reaction, empty/environment, prop, and simple-action shots.

## 3. Automated technical QC

Every selected asset and final render is checked for:

- decodability and non-empty duration;
- MP4/H.264/yuv420p video, 720x1280, 30 fps;
- AAC audio at 48 kHz and expected channel layout;
- final duration between 60 and 90 seconds;
- black-frame, frozen-frame, silence, clipping, missing-track, and corrupted-packet thresholds;
- subtitle parseability, safe-area placement, timing order, and dialogue coverage;
- asset hash, immutable storage reference, lineage, model route, operation, cost, and rights facts.

Technical-profile acceptance is at least 95% across generated candidate assets and 100% for selected final deliverables.

## 4. Human creative rubric

Two reviewers independently score each final fixture and a stratified sample of candidate shots. Disagreement greater than one point is adjudicated by Product Owner.

| Dimension | Scale | Release threshold |
| --- | --- | --- |
| Story clarity and pacing | 1–5 | average at least 3.5 |
| Main-character identity | pass/fail by shot | at least 85% pass |
| Costume/location/prop continuity | pass/fail by dependency | at least 80% pass |
| Dialogue intelligibility and sync | 1–5 | average at least 4.0 |
| Composition and motion usefulness | 1–5 | average at least 3.5 |
| Content/rights safety | pass/fail | 100% pass or reviewed block |

At least 75% of selected shots must not require manual regeneration. Creative repair is capped at two attempts per stable Shot; the next failure creates a human Issue.

## 5. VLM QC contract

The VLM returns schema-valid JSON only:

```json
{
  "schema_version": "qc.v1",
  "asset_version_id": "...",
  "model_route_version": "...",
  "issues": [
    {
      "code": "IDENTITY_DRIFT",
      "severity": "BLOCKING",
      "time_range_ms": [0, 1200],
      "confidence": 0.0,
      "evidence": "concise observable fact",
      "repair_hint": "bounded recommendation"
    }
  ]
}
```

Allowed initial codes are `TECHNICAL_PROFILE`, `BLACK_FRAME`, `SILENCE`, `SUBTITLE_SYNC`, `IDENTITY_DRIFT`, `COSTUME_DRIFT`, `LOCATION_DRIFT`, `PROP_DRIFT`, `LIP_SYNC`, `MOTION_ARTIFACT`, `NARRATIVE_MISMATCH`, and `CONTENT_SAFETY`.

VLM recommendations are compared with the labeled regression set. Blocking issue recall must be at least 90%, precision at least 75%, and schema-valid output 100%. Until those thresholds pass, VLM QC is advisory and cannot automatically reject or repair an asset.

## 6. Scenarios and recovery evidence

The release suite covers all approved scenarios A–G: full creation, single-shot failure, service interruption, dialogue edit, shot replacement, budget exhaustion, and content/rights risk.

Every run exports an `EvidenceManifest` containing:

- source fixture and immutable input hashes;
- state transitions, Operations, ProviderAttempts, Jobs, callbacks and reconciliation;
- prompts and parameters after secret/personal-data redaction;
- asset hashes, ffprobe results, subtitle/audio checks and lineage;
- human and VLM QC reports, Issues and repair cycles;
- BudgetReservations, CostEvents and route prices;
- final render hash, screenshots, failure injections and recovery proof.

## 7. Stage gates

- Week 8 real-generation Gate: all five fixtures complete and no duplicate paid operation; quality shortfalls may remain only as explicit P1 issues.
- Week 12 real-MVP Gate: every metric in this specification passes and all P0/P1 release blockers are closed.
- Week 21–24 Beta Gate: the same regression suite remains green against pinned production routes before every expansion.

`WEEK_02_EVALUATION_SPEC = READY_FOR_PRODUCT_OWNER_REVIEW`

