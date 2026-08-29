# 06_DATA_CONTRACTS.md — Canonical Domain Contracts

Status: Draft for Product Owner review. This document and `07_STATE_MACHINES.md` form one specification unit. It defines logical contracts, not a Prisma schema, SQL migration, provider SDK payload, or production implementation.

## 1. Scope and authority

These contracts refine `INTENT.md`, `02_DECISIONS.md`, `03_PRODUCT_SPEC.md`, `04_USER_FLOWS.md`, `EXPLORE_REPORT.md`, `SPIKE_EVIDENCE.md`, and `05_ARCHITECTURE.md`. `INTENT.md` and accepted decisions remain higher authority. When older documents use `COMPLETED` or project-wide `WAITING_USER`, this specification applies the later approved completion model and local-issue semantics without editing those documents.

Canonical rules:

1. PostgreSQL is the queryable source of domain truth; workflow history is not.
2. IDs are opaque UUID/ULID values unless a deterministic logical ID is explicitly required.
3. Every workspace-owned row carries `workspace_id`; every project-owned row also carries `project_id`.
4. Version rows are immutable after commit. Mutable aggregate rows point to committed versions.
5. All state changes use the machines and transition authority in `07_STATE_MACHINES.md`.
6. Published asset bytes, CostEvents, EvidenceRecords, inbox receipts, outbox events, and audit transitions are append-only.
7. Soft deletion hides an aggregate; it never erases audit, cost, evidence, lineage, or legal-retention facts.

## 2. Common field conventions

| Concern | Canonical contract |
|---|---|
| IDs | `<entity>_id`; opaque, globally unique, never reused |
| Ownership | `workspace_id` required; `project_id` required where project-scoped |
| Optimistic concurrency | mutable aggregates use integer `row_version`; commands provide `expected_row_version` |
| Time | UTC RFC 3339 at boundaries; timezone-aware database timestamp internally |
| Audit | `created_at`, `created_by_actor_id`, `updated_at`, `updated_by_actor_id`; transitions add correlation and causation IDs |
| Deletion | `deleted_at`, `deleted_by_actor_id`, `deletion_reason`; null means active |
| External identifiers | scoped by provider/account/region; never used as internal identity |
| Hashes | algorithm plus lowercase digest, normally SHA-256 |
| Structured payloads | carry `schema_name`, `schema_version`, and optionally `contract_version` |
| Currency | ISO 4217 uppercase code and integer minor units only |
| Ordering | explicit integer `ordinal` or rational/time offset; never inferred from creation time |
| Idempotent command | `command_id` unique per workspace and command type, with persisted outcome |

References point to stable aggregate IDs or immutable version IDs deliberately. A creative input to a paid operation must reference immutable versions.

## 3. Identity and tenancy

### 3.1 Workspace

- **Purpose:** tenancy and authorization boundary.
- **Identity/ownership:** stable `workspace_id`; self-owned tenancy root.
- **References:** default budget/currency policy and membership records (membership is outside this document's required entity list).
- **Versioning:** mutable aggregate with `row_version`; material policy changes are audit events.
- **Immutable:** `workspace_id`, `created_at`.
- **Mutable:** `display_name`, `status`, default currency, policy references.
- **Uniqueness:** normalized workspace slug unique among non-deleted workspaces.
- **Lifecycle/audit/delete:** `ACTIVE`, `SUSPENDED`, `CLOSED`; soft-delete/retention only.
- **Invariants:** every Actor and project belongs to exactly one Workspace; cross-workspace references are forbidden.

### 3.2 Actor

- **Purpose:** audited principal for humans and services.
- **Identity/ownership:** stable `actor_id`, exactly one `workspace_id` for MVP.
- **References:** authentication subject for humans or service-principal key for systems; role grants.
- **Versioning:** mutable aggregate with audited role/status changes.
- **Immutable:** `actor_id`, `workspace_id`, `actor_type`, authentication issuer/subject tuple once bound.
- **Mutable:** display name, status, role grants.
- **Uniqueness:** `(workspace_id, auth_issuer, auth_subject)` when authenticated.
- **Lifecycle/audit/delete:** `ACTIVE`, `DISABLED`; disabling preserves attribution; never hard-delete referenced Actors.
- **Invariants:** system actors are named and least-privileged; adapters act through an authorized application-service actor, never impersonate a human.

## 4. Project contracts

### 4.1 Project

- **Purpose:** stable creator-visible production aggregate and durable lifecycle holder.
- **Identity/ownership:** `project_id`, `workspace_id`.
- **References:** `current_project_version_id`, `active_timeline_version_id`, `budget_id`.
- **Versioning:** Project is mutable shell; creative configuration lives in immutable ProjectVersion.
- **Immutable:** IDs and initial creator.
- **Mutable:** title, durable `lifecycle_state`, pause/cancel intent, current-version pointers.
- **Uniqueness:** optional normalized title is not globally unique; commands use `project_id`.
- **Lifecycle fields:** lifecycle state only; execution gate and health are separate projections in Section 16.
- **Audit/delete:** common audit, transition log, soft-delete after cancellation/retention checks.
- **Invariants:** one active committed ProjectVersion; local Shot issues never change Project lifecycle to `WAITING_HUMAN`; `ACCEPTED` requires an accepted deliverable Review.

### 4.2 ProjectVersion

- **Purpose:** immutable snapshot of all production-driving intent.
- **Identity/ownership:** `project_version_id`, workspace/project, monotonic `version_number`.
- **References:** ProductionBrief, StoryBible, Screenplay, creative-asset versions, ShotVersions/ShotSpecs, graph version.
- **Versioning:** immutable after `COMMITTED`; draft editing creates a new draft version or child records.
- **Immutable after commit:** all content, parent version, content hash, reason.
- **Mutable before commit:** draft content references and validation result.
- **Uniqueness:** `(project_id, version_number)`; at most one active draft per editing session/command policy.
- **Lifecycle fields:** `DRAFT`, `COMMITTED`, `SUPERSEDED` (selection status, not deletion).
- **Audit/delete:** committed versions cannot be deleted while referenced; draft may be discarded.
- **Invariants:** every paid Operation binds one committed ProjectVersion; rollback creates/selects a new current version and never rewrites history.

### 4.3 ProductionBrief

- **Purpose:** normalized creator goals, constraints, rights declaration, output profile, and approved spend boundary.
- **Identity/ownership:** stable `production_brief_id`; versioned under ProjectVersion.
- **References:** source input AssetVersions, rights EvidenceRecords, Budget.
- **Versioning:** immutable committed versions.
- **Immutable after commit:** source text/hash, target duration, aspect/output constraints, language, rights facts, forbidden content, quality/cost preference.
- **Mutable:** draft fields only.
- **Uniqueness:** one committed brief per ProjectVersion.
- **Lifecycle/audit/delete:** draft/committed; retained with ProjectVersion.
- **Invariants:** target defaults to 60 seconds and approved range is 60–90 seconds; paid execution requires confirmed rights and budget.

### 4.4 StoryBible

- **Purpose:** versioned narrative truth: premise, beats, tone, character/location/prop references, continuity rules.
- **Identity/ownership:** `story_bible_id`, project version.
- **References:** immutable Character/Location/Prop versions and Screenplay.
- **Versioning:** immutable version with parent and change reason.
- **Immutable after commit:** structured content, schema version, referenced version IDs, content hash.
- **Mutable:** draft only.
- **Uniqueness:** one selected StoryBible version per ProjectVersion.
- **Lifecycle/audit/delete:** draft/committed/superseded; no hard deletion when downstream lineage exists.
- **Invariants:** references never float to mutable “latest”; changes require an Impact Plan.

## 5. Story contracts

### 5.1 Screenplay

- **Purpose:** ordered, structured dramatic content rather than an opaque prompt.
- **Identity/ownership:** `screenplay_id`, project and immutable screenplay version ID/version number.
- **References:** ordered Scene versions and StoryBible version.
- **Versioning:** committed versions are immutable; edits create a child version.
- **Immutable after commit:** scene order, dialogue/action content references, source provenance, content hash.
- **Mutable:** draft only.
- **Uniqueness:** `(project_id, screenplay_id, version_number)`.
- **Lifecycle/audit/delete:** draft/committed/superseded; versions remain auditable.
- **Invariants:** total estimated duration must be recorded; a dialogue edit identifies exact affected content IDs for impact analysis.

### 5.2 Scene

- **Purpose:** ordered dramatic unit with place, time, participants, action, and continuity facts.
- **Identity/ownership:** stable `scene_id`; immutable `scene_version_id`.
- **References:** Screenplay version, Location version, Characters, Props, ordered screenplay content.
- **Versioning:** immutable versions.
- **Immutable after commit:** scene heading, narrative time, referenced versions, ordered content, content hash.
- **Mutable:** draft only.
- **Uniqueness:** scene ordinal unique within a Screenplay version.
- **Lifecycle/audit/delete:** superseded rather than overwritten; removal in a later Screenplay does not erase prior Scene versions.
- **Invariants:** referenced characters/looks/locations/props belong to the same workspace/project context.

### 5.3 Dialogue and screenplay content

- **Purpose:** addressable content units for local invalidation and audio/subtitle lineage.
- **Identity/ownership:** stable `content_id`; immutable `content_version_id`; project/scene ownership.
- **References:** speaker Character, language, optional performance direction and source span.
- **Versioning:** immutable versions; content types include `DIALOGUE`, `ACTION`, `TRANSITION`, `CAPTION`, `VOICEOVER`.
- **Immutable after commit:** type, text, speaker, ordinal, timing intent, source provenance/hash.
- **Mutable:** draft only.
- **Uniqueness:** ordinal unique within Scene version; stable content ID persists across semantically same edits.
- **Lifecycle/audit/delete:** omission creates a later screenplay version; history retained.
- **Invariants:** TTS, subtitle, lip-sync, and affected ShotSpecs bind a content version, never unversioned text.

## 6. Creative asset contracts

### 6.1 Character

- **Purpose:** stable narrative identity across looks and shots.
- **Identity/ownership:** `character_id`, workspace/project.
- **References:** selected CharacterLook version, source StoryBible.
- **Versioning:** stable shell plus immutable descriptive versions where traits change.
- **Immutable:** identity and project ownership.
- **Mutable:** display name, selected look pointer, active flag.
- **Uniqueness:** optional canonical code unique per project.
- **Lifecycle/audit/delete:** inactive/soft-deleted only; prior versions remain.
- **Invariants:** visual generations reference an explicit CharacterLook version.

### 6.2 CharacterLook

- **Purpose:** immutable appearance/wardrobe configuration used by generation and continuity.
- **Identity/ownership:** `character_look_id`, `character_look_version_id`, workspace/project/character.
- **References:** reference AssetVersions, rights EvidenceRecords, structured traits.
- **Versioning:** immutable versions; selected pointer lives on Character or ProjectVersion.
- **Immutable after commit:** appearance attributes, wardrobe, references, constraints, hash.
- **Mutable:** draft only.
- **Uniqueness:** version number unique per look identity.
- **Lifecycle/audit/delete:** committed/superseded; retained when used.
- **Invariants:** changing selected look always computes an Impact Plan through typed edges.

### 6.3 Location

- **Purpose:** stable place identity and versioned visual/spatial state.
- **Identity/ownership:** `location_id`, immutable version ID, workspace/project.
- **References:** reference assets, rights evidence, Scene versions.
- **Versioning:** immutable versions.
- **Immutable after commit:** layout, lighting/time constraints, visual description, references/hash.
- **Mutable:** display/selection pointers only on aggregate shell.
- **Uniqueness:** canonical code unique per project when supplied.
- **Lifecycle/audit/delete:** soft-delete shell; preserve referenced versions.
- **Invariants:** Scene and ShotSpec reference explicit Location versions.

### 6.4 Prop

- **Purpose:** stable prop identity plus versioned ownership, appearance, and continuity state.
- **Identity/ownership:** `prop_id`, immutable version ID, workspace/project.
- **References:** holder Character, Location, reference AssetVersions.
- **Versioning:** immutable descriptive/state versions.
- **Immutable after commit:** physical description and continuity snapshot.
- **Mutable:** selected version pointer/active flag.
- **Uniqueness:** canonical code unique per project when supplied.
- **Lifecycle/audit/delete:** retained with prior scenes/shots.
- **Invariants:** state change (holder, damage, visibility) produces a new version and Impact Plan where referenced.

## 7. Shot system contracts

### 7.1 Shot

- **Purpose:** stable, independently executable production unit.
- **Identity/ownership:** `shot_id`, workspace/project, stable scene association.
- **References:** `current_shot_version_id`, selected candidate AssetVersion, open Issues.
- **Versioning:** mutable aggregate shell over immutable ShotVersions.
- **Immutable:** identity and original project.
- **Mutable:** lifecycle state, selected-version pointers, local repair count, cancellation intent.
- **Uniqueness:** human-readable shot code unique per project; not the primary key.
- **Lifecycle/audit/delete:** follows Shot machine; removed shots are superseded/cancelled, not erased.
- **Invariants:** `creative_repair_cycles_used` is shot-level, persists across jobs/operations, and cannot be reset by changing IDs; maximum is 2 unless Product Owner changes DEC-012.

### 7.2 ShotVersion

- **Purpose:** immutable snapshot of production intent and selections for one Shot.
- **Identity/ownership:** `shot_version_id`, shot/project/workspace, monotonic version.
- **References:** ShotSpec, source Scene/content/creative versions, candidates, selected asset.
- **Versioning:** immutable after commit; parent and change reason required.
- **Immutable after commit:** all references, strategy version, content hash.
- **Mutable:** draft only.
- **Uniqueness:** `(shot_id, version_number)`.
- **Lifecycle/audit/delete:** draft/committed/superseded/invalidated; retained.
- **Invariants:** operations and graph edges bind ShotVersion, not merely Shot.

### 7.3 ShotSpec

- **Purpose:** canonical structured generation/QC contract for a ShotVersion.
- **Identity/ownership:** `shot_spec_id`, project/shot/version.
- **References:** exact Scene/content/CharacterLook/Location/Prop/Asset versions.
- **Versioning:** immutable; carries `schema_name=shot_spec`, `schema_version`, and `contract_version`.
- **Immutable after commit:** narrative purpose, duration, action/dialogue refs, continuity in/out, framing/camera, generation route/strategy, candidate policy, quality targets, cost ceiling, repair policy.
- **Mutable:** draft only.
- **Uniqueness:** one committed ShotSpec per ShotVersion.
- **Lifecycle/audit/delete:** retained with ShotVersion.
- **Invariants:** natural-language prompt is derived data, never sole truth; duration and all production inputs are explicit and versioned.

### 7.4 DependencyEdge

- **Purpose:** versioned execution, derivation, continuity, synchronization, and invalidation relation; never playback order.
- **Identity/ownership:** `dependency_edge_id`, graph/project version, workspace/project.
- **References:** typed source and target entity/version IDs.
- **Versioning:** immutable as part of a graph version; edits create a new graph version.
- **Immutable:** type, endpoints, policy flags, reason, schema version.
- **Mutable:** none after commit.
- **Uniqueness:** `(graph_version_id, edge_type, source_ref, target_ref, policy_key)`.
- **Lifecycle/audit/delete:** omission from later graph supersedes; historical edges remain.
- **Invariants:** endpoint types must be permitted by the edge contract below.

| Edge type | Direction | Blocks execution | Propagates invalidation | Cycles | Version behavior |
|---|---|---:|---:|---|---|
| `EXECUTION_REQUIRES` | prerequisite version → dependent operation/ShotVersion | yes, until prerequisite is usable | yes when prerequisite version becomes invalid | forbidden | binds exact versions; new prerequisite requires a new edge/impact plan |
| `DERIVED_FROM` | source version → derived AssetVersion/data version | no scheduler block by itself | yes | forbidden | immutable lineage edge; never retargeted |
| `CONTINUITY_REFERENCE` | reference state/version → consuming ShotVersion | no by default | no by default; explicit policy may flag review | allowed only if it does not form an execution/invalidation cycle | exact version plus continuity role; change produces review/impact candidates |
| `AUDIO_SYNC` | audio/dialogue version → lip-sync/video/timeline consumer | yes where synchronized output is required | yes | forbidden | exact timing/content version; replacement invalidates synchronized descendants |
| `INVALIDATES_ON_CHANGE` | watched version/field set → dependent version/operation class | no runtime prerequisite | yes according to declared field mask and scope | forbidden in invalidation subgraph | policy is versioned; impact traversal records edge IDs and graph version |

The execution and invalidation subgraphs must be acyclic. TimelineClip order never creates a DependencyEdge. Continuity cycles may describe mutual comparison only when explicitly non-blocking and non-propagating.

## 8. Timeline contracts

### 8.1 Timeline

- **Purpose:** stable editable assembly identity.
- **Identity/ownership:** `timeline_id`, workspace/project.
- **References:** selected `timeline_version_id`.
- **Versioning:** shell plus immutable TimelineVersions.
- **Immutable:** identity/ownership.
- **Mutable:** active version pointer and archival status.
- **Uniqueness:** one primary Timeline per project for MVP.
- **Lifecycle/audit/delete:** archive/soft-delete only; accepted deliverable version retained.
- **Invariants:** it represents playback composition, not production dependency.

### 8.2 TimelineVersion

- **Purpose:** immutable renderable composition snapshot.
- **Identity/ownership:** `timeline_version_id`, timeline/project/workspace, version number.
- **References:** ordered TimelineClips, caption/audio assets, render spec, parent version.
- **Versioning:** immutable committed versions; carries timeline schema/contract versions.
- **Immutable after commit:** clip set/order, tracks, transitions, output profile, input hashes.
- **Mutable:** draft only.
- **Uniqueness:** `(timeline_id, version_number)`.
- **Lifecycle/audit/delete:** draft/committed/rendered/superseded; accepted version retained.
- **Invariants:** every clip references an immutable AssetVersion; replacement creates a new TimelineVersion; final render provenance includes exact version.

### 8.3 TimelineClip

- **Purpose:** one placed media interval on a timeline track.
- **Identity/ownership:** `timeline_clip_id`, TimelineVersion/project/workspace.
- **References:** AssetVersion, optional ShotVersion/content version.
- **Versioning:** immutable with TimelineVersion.
- **Immutable:** track type, ordinal/z-order, timeline start, source in/out, duration, gain/transform/transition.
- **Mutable:** none after commit.
- **Uniqueness:** clip ID within version; video intervals follow overlap policy.
- **Lifecycle/audit/delete:** removed only by creating a new TimelineVersion.
- **Invariants:** source range is within asset probe duration; clip order does not imply execution dependency.

## 9. Media contracts

### 9.1 Asset

- **Purpose:** stable logical media/document identity across immutable byte versions.
- **Identity/ownership:** `asset_id`, workspace/project; optional scene/shot association.
- **References:** current/selected AssetVersion, lineage, rights evidence.
- **Versioning:** shell plus immutable AssetVersions.
- **Immutable:** identity, media role, ownership.
- **Mutable:** selection/archive/delete-pending pointers; not bytes.
- **Uniqueness:** optional logical role key scoped to owning entity; never storage path alone.
- **Lifecycle/audit/delete:** Asset state follows machine; deletion is mark-and-sweep after retention/reference checks.
- **Invariants:** published bytes are never overwritten; selection is relational state, not mutation of a version.

### 9.2 AssetVersion

- **Purpose:** immutable published bytes and validated metadata.
- **Identity/ownership:** `asset_version_id`, Asset/project/workspace, monotonic version.
- **References:** storage logical key, content hash, producer Operation, probe/QC Evidence, lineage parents.
- **Versioning:** each different byte payload is a new version.
- **Immutable after publish:** storage key, hash, size, MIME/container/codec/probe metadata, producing operation, creation tool/model/schema versions.
- **Mutable:** lifecycle before publication; quarantine/deletion eligibility after publication does not change bytes.
- **Uniqueness:** `(workspace_id, content_hash, media_role)` may deduplicate physical storage, but logical AssetVersion identity remains explicit; storage key unique.
- **Lifecycle/audit/delete:** temporary → validated → published; published can be selected/superseded/quarantined/delete-pending. Physical delete only when no retained reference/legal hold; tombstone remains.
- **Invariants:** metadata finalization happens only after immutable publish succeeds; database must never advertise unpublished bytes as published.

### 9.3 AssetLineage

- **Purpose:** immutable directed provenance between versioned inputs and outputs.
- **Identity/ownership:** `asset_lineage_id`, workspace/project.
- **References:** source entity/version, target AssetVersion, producing Operation, relation type.
- **Versioning:** append-only edges.
- **Immutable:** endpoints, relation, operation, parameters hash, created audit.
- **Mutable:** none.
- **Uniqueness:** same source/target/relation/operation tuple once.
- **Lifecycle/delete:** never soft-deleted independently; follows retained evidence.
- **Invariants:** lineage is acyclic for byte derivation; example chain is source asset → derived keyframe → generated video → lip-sync result → selected asset → TimelineClip. Selection and placement are recorded without overwriting earlier bytes.

### 9.4 Storage publish contract

The Storage port exposes semantics, not filesystem primitives:

1. `begin_temporary_write(job_id, expected_media_type)` returns an isolated temporary handle.
2. bytes are written and closed; validation/probe and hash run against the closed temporary object.
3. `publish_immutable(handle, content_hash, logical_key)` commits bytes exactly once or returns the existing identical object.
4. application transaction finalizes AssetVersion metadata, lineage, EvidenceRecord, and outbox event.
5. orphan reconciliation removes expired temporary objects and detects published objects lacking metadata.

Local storage may use fsync/rename; S3/OSS may use multipart completion/copy/conditional put. Rename is not a domain guarantee.

## 10. Execution contracts

### 10.1 Operation

- **Purpose:** one logical side effect, especially one potentially paid provider action.
- **Identity/ownership:** deterministic stable `operation_id`, workspace/project.
- **References:** exact ProjectVersion, target version, operation type, route/strategy version, BudgetReservation, ProviderAttempts, resulting AssetVersions.
- **Versioning:** logical intent is immutable; a materially new intent is a new Operation.
- **Immutable:** identity inputs, canonical intent hash, paid flag, created correlation/causation.
- **Mutable:** lifecycle state, resolved ProviderAttempt/result, cancellation intent, terminal reason.
- **Uniqueness:** `operation_id` primary uniqueness plus `(workspace_id, canonical_intent_hash, operation_type)` guard where applicable.
- **Lifecycle/audit/delete:** follows Operation machine; never deleted while costs/evidence/attempts exist.
- **Invariants:** retry never invents a new operation; `SUBMISSION_UNKNOWN` must reconcile before resubmission.

#### Stable `operation_id` semantics

Canonical ID input is a length-delimited, normalized tuple hashed under a versioned namespace:

```text
operation-id/v1(
  workspace_id,
  project_id,
  project_version_id,
  target_type,
  target_id,
  target_version_id,
  operation_type,
  input_version_ids_and_hashes,
  generation_route_id,
  strategy_version,
  candidate_slot_or_purpose
)
```

Ordering and null representation are canonical; secrets, timestamps, attempt numbers, transport request IDs, and worker IDs are excluded.

| Event | `operation_id` behavior |
|---|---|
| transport retry (timeout/429/recoverable 5xx before known result) | same Operation and ID |
| provider reconciliation after unknown response | same Operation and ID; may add observations/attempt facts, never blind submit |
| creative repair | new Operation because strategy/input intent changes; same Shot repair ledger increments exactly once when repair is authorized |
| intentional new candidate | new Operation through distinct immutable `candidate_slot_or_purpose`; does not consume repair budget |
| user-triggered regeneration | new Operation only when command explicitly creates new candidate/strategy/input intent; repeated delivery of the same command returns the prior Operation |
| deterministic media retry | same Operation and render spec; a changed render spec is a new Operation |

### 10.2 ProviderAttempt

- **Purpose:** one bounded interaction/submission path with an external provider for an Operation.
- **Identity/ownership:** `provider_attempt_id`, workspace/project/operation.
- **References:** provider/account/region/model version, request/response contract versions, external job ID/client reference, callbacks, costs/evidence.
- **Versioning:** append one attempt per deliberate provider interaction; observations append as events.
- **Immutable:** provider selection, normalized request hash, attempt ordinal, client reference.
- **Mutable:** lifecycle state, external job ID, last observation, terminal normalized result.
- **Uniqueness:** `(operation_id, attempt_ordinal)` and provider-scoped client reference; external job ID unique within provider account/region when supplied.
- **Lifecycle/audit/delete:** retained; raw payloads redacted and retention-limited.
- **Invariants:** adapters report facts; only application service transitions domain Operation/Shot. An attempt cannot authorize spend.

### 10.3 Job

- **Purpose:** schedulable internal work item for provider interaction, reconciliation, media, QC, or projection.
- **Identity/ownership:** `job_id`, workspace/project; references Operation where side-effecting.
- **Versioning:** immutable input payload and handler/contract version; retries are executions of same Job unless a new logical work item is required.
- **Immutable:** job type, input reference/hash, queue policy, operation link.
- **Mutable:** lifecycle, retry counters by taxonomy, lease heartbeat for worker execution only, result/error facts.
- **Uniqueness:** application-defined idempotency key per logical Job.
- **Lifecycle/audit/delete:** follows Job machine; retained per evidence policy.
- **Invariants:** Job retry counters never alter Shot creative repair count; a Job is not a ProviderAttempt or creative candidate.

## 11. Quality and human review

### 11.1 Review

- **Purpose:** immutable assessment and disposition of a versioned subject.
- **Identity/ownership:** `review_id`, workspace/project.
- **References:** exact subject version, reviewer Actor/subsystem, Evidence, Issue IDs.
- **Versioning:** each rerun or human decision creates a new Review; prior Review is not overwritten.
- **Immutable after completion:** review type, criteria/schema/model/tool versions, findings, scores, decision, input hashes.
- **Mutable:** lifecycle until completed/cancelled.
- **Uniqueness:** optional `(subject_version, review_type, criteria_version, invocation_id)`.
- **Lifecycle/audit/delete:** retained with subject and acceptance evidence.
- **Invariants:** abstract score alone cannot pass; findings include issue codes and actionable evidence. Final acceptance is human/Product Owner authority.

### 11.2 Issue

- **Purpose:** local or global actionable problem requiring automated repair, human choice, or accepted risk.
- **Identity/ownership:** `issue_id`, workspace/project.
- **References:** `affected_entity_type/id/version`, originating Review/Evidence, optional global gate reason.
- **Versioning:** mutable lifecycle with append-only transition/resolution history.
- **Immutable:** issue type, original reason, affected entity, origin, opened audit.
- **Mutable minimum:** `status`, `allowed_actions`, `resolution`, `resolved_by_actor_id`, `resolved_at`; severity/owner may be updated by authorized commands.
- **Uniqueness:** dedupe key `(project_id, issue_type, affected_version, reason_code, active)` prevents duplicate active cards.
- **Lifecycle/audit/delete:** follows Issue machine; never hard-delete.
- **Invariants:** MVP has no domain lease/expiry semantics. Worker leases belong to Job execution, not human Issues. A Shot-level Issue is local and cannot create a global execution gate.

## 12. Money contracts

### 12.1 Money value

```text
Money { amount_minor: int64, currency: ISO-4217 }
```

`CNY ¥12.34` is `amount_minor=1234`, `currency=CNY`. Floating point is forbidden. Currency conversion, if later introduced, produces explicit rate/version and adjustment events; amounts of different currencies are never summed directly.

### 12.2 Budget

- **Purpose:** approved spend ceiling and aggregation root.
- **Identity/ownership:** `budget_id`, workspace/project.
- **References:** approving Actor/Evidence, reservations and CostEvents.
- **Versioning:** ceiling changes are append-only approvals or immutable budget revisions; current pointer is mutable.
- **Immutable:** currency for MVP, initial approval facts.
- **Mutable:** current approved limit through authorized command only; status.
- **Uniqueness:** one active project Budget per currency for MVP.
- **Lifecycle/audit/delete:** active/closed/cancelled; retained.
- **Invariants:** actual + active reservations + proposed upper bound must not exceed approved limit in one serialized transaction.

### 12.3 BudgetReservation

- **Purpose:** atomic upper-bound hold before paid submission.
- **Identity/ownership:** `budget_reservation_id`, workspace/project/budget; exactly one Operation.
- **References:** Operation and later CostEvents.
- **Versioning:** mutable state, immutable amount/currency after creation; changes use release plus new reservation or adjustment events.
- **Immutable:** operation, upper bound, currency, pricing context.
- **Mutable:** lifecycle state, settled/released amounts and terminal audit.
- **Uniqueness:** one active reservation per Operation; `(budget_id, operation_id)` unique.
- **Lifecycle/audit/delete:** follows reservation machine; never delete.
- **Invariants:** created transactionally with capacity check; only application service settles/releases.

### 12.4 CostEvent

- **Purpose:** append-only monetary fact.
- **Identity/ownership:** `cost_event_id`, workspace/project.
- **References:** Budget, reservation, Operation, ProviderAttempt, optional scene/shot allocation.
- **Versioning:** append-only; corrections are new events.
- **Immutable:** `event_type`, Money, occurred/recorded time, pricing version, source fact, mock/real indicator, allocation rule.
- **Mutable:** none; reconciliation adds another event.
- **Uniqueness:** provider invoice/event reference scoped to provider account plus event type; otherwise deterministic source-event key.
- **Lifecycle/audit/delete:** never deleted.
- **Invariants and semantics:**
  - `ESTIMATE`: non-ledger forecast; does not consume budget.
  - `RESERVATION`: mirrors an authorized hold; not actual spend.
  - `ACTUAL`: confirmed incurred charge, including a charge discovered after cancellation.
  - `ADJUSTMENT`: signed correction with reason and predecessor reference.
  - `REFUND`: signed credit tied to an actual charge; never erases it.
  - failed/no-charge observations use an explicit zero-amount fact or evidence type, not a fabricated actual cost.

## 13. Evidence and infrastructure contracts

### 13.1 EvidenceRecord

- **Purpose:** exportable, verifiable index of material facts and artifacts.
- **Identity/ownership:** `evidence_record_id`, workspace/project.
- **References:** typed subject, logical URI, AssetVersion or external retained record, correlation/causation IDs.
- **Versioning:** append-only; carries evidence schema/contract version.
- **Immutable:** type, subject version, content hash, tool/model/schema versions, actor, timestamp, verification result.
- **Mutable:** none; a re-verification adds a new record.
- **Uniqueness:** deterministic evidence source key where available.
- **Lifecycle/delete:** retained per compliance; secrets/signed URLs excluded or redacted.
- **Invariants:** Evidence is an index, not a duplicate log store; state transitions, costs, provider uncertainty, media probe/hash, QC, recovery and final render are covered.

### 13.2 EventOutbox

- **Purpose:** reliably publish progress/domain events after database commit.
- **Identity/ownership:** `outbox_event_id`, workspace/project, aggregate ID/version.
- **References:** transaction/correlation/causation IDs.
- **Versioning:** immutable event payload with event schema version.
- **Immutable:** event type, payload, aggregate sequence, committed timestamp.
- **Mutable:** delivery attempt metadata and published timestamp only.
- **Uniqueness:** `(aggregate_type, aggregate_id, aggregate_sequence)` and event ID.
- **Lifecycle/delete:** retained/replayed by cursor policy; compaction never removes authoritative domain facts.
- **Invariants/transaction boundary:** domain mutation, transition/audit record, and outbox insert commit in the same PostgreSQL transaction. Publishing happens only after commit; at-least-once delivery is expected, consumers dedupe by event ID and sequence. No event is published from uncommitted workflow memory.

### 13.3 CallbackInbox

- **Purpose:** authenticate, deduplicate, order, and replay provider callbacks before application processing.
- **Identity/ownership:** `callback_inbox_id`, workspace/project if resolvable.
- **Deduplication fields:** provider, account/tenant, endpoint/event type, provider event ID; if absent, canonical payload hash plus signed timestamp/window and external job reference.
- **References:** ProviderAttempt/Operation/external job ID after resolution.
- **Versioning:** immutable raw-envelope hash and parser/contract version; normalized processing result append/audit fields.
- **Immutable:** receipt time, headers allowlist/signature result, raw payload hash/encrypted pointer, provider event key.
- **Mutable:** processing state, attempt count, normalized event time/sequence, processed/error time.
- **Uniqueness:** provider-scoped event key; fallback hash/window key.
- **Replay/ordering metadata:** provider sequence if available, provider occurred time, received time, predecessor token, late/out-of-order flag, replay count, last processing version.
- **Lifecycle/delete:** retained per provider/security policy; never re-executes a domain transition without idempotency checks.
- **Invariants:** verify signature and replay window before interpretation; store receipt before processing; duplicates return success without duplicate effects; ordering gaps trigger reconciliation rather than guessed transitions.

## 14. Schema and contract versioning

`schema_version` identifies the shape/semantics of stored or exchanged data. `contract_version` identifies compatibility rules for a boundary. Versions are immutable strings or integers under a named schema; producer/consumer versions and raw hashes are retained.

| Payload | Required version facts | Compatibility rule |
|---|---|---|
| ShotSpec | schema name/version, strategy version, content hash | migrations create a new interpreted version; old raw version remains |
| provider request | internal canonical contract version, adapter mapping version, provider API/model version, request hash | retry same Operation reuses same canonical request; adapter evolution cannot silently change intent |
| provider response/callback | raw payload hash/pointer, provider API version, parser version, normalized contract version | unknown versions are quarantined/reconciled, not guessed |
| Evidence | evidence schema version, producing tool/model version, verifier version | old Evidence remains valid as historical bytes; new verifier produces a new record |
| Timeline | timeline schema/contract version, render spec/tool version | render only with a supported interpreter; migration creates a new TimelineVersion |
| workflow payload | workflow contract version, command/event schema versions, minimum supported worker version | unsupported payload pauses/raises Issue; never assume future code can replay every old payload |

Compatibility is explicit: `READ_EXACT`, `READ_WITH_MIGRATOR`, or `UNSUPPORTED`. Migrators are deterministic, version-pinned, preserve original payload/hash, and emit evidence. An unsupported old payload is a controlled failure, not silent coercion.

## 15. Impact Plan contract

Any approved change to dialogue, CharacterLook, keyframe, selected candidate, Scene/Location, or Prop state first produces an immutable `ImpactPlan` (logical contract; it may be stored as a versioned workflow payload/EvidenceRecord):

- change command and exact before/after version IDs;
- graph version and traversed DependencyEdge IDs;
- affected ShotVersions, AssetVersions, Operations, Reviews, and TimelineVersions;
- action per target: `KEEP`, `REVIEW`, `INVALIDATE`, `REGENERATE`, `RERENDER`;
- estimated Money/reservations and whether human cost approval is required;
- explanation and minimality evidence;
- approving Actor/command and resulting new version IDs.

Old versions and bytes remain auditable. Impact execution creates new versions/operations and marks old selections superseded or invalidated; it never rewrites lineage.

## 16. Derived projections, not sources of truth

The following are rebuildable projections:

- project execution gate (open gate reasons that prohibit new paid work);
- project health such as `RUNNING_WITH_ISSUES`;
- progress counts and current stage;
- actual/reserved/remaining spend by project/scene/shot;
- selected asset and current Timeline summaries;
- Evidence Manifest and Cost Report.

Projections never originate state transitions. If they disagree with authoritative aggregates/ledgers, rebuild them from committed facts.

## 17. Cross-contract invariants

1. No project/workspace cross-reference is permitted.
2. Every paid submission has one stable Operation, an atomic BudgetReservation, ProviderAttempt facts, and eventual CostEvent reconciliation.
3. `SUBMISSION_UNKNOWN` cannot trigger an automatic new paid submission.
4. Only a QC-driven strategy-changing creative repair increments the persistent Shot repair counter.
5. A local Issue cannot globally stop independent Shots; only explicit project-wide gate reasons can block new paid work.
6. Timeline order and DependencyEdge semantics never substitute for one another.
7. Published bytes, lineage, costs, evidence, callbacks, and transition history are immutable/append-only.
8. Every state-bearing entity uses `07_STATE_MACHINES.md`; adapters report facts through application commands.

## Gate

DATA_CONTRACTS_GATE = READY_FOR_REVIEW
