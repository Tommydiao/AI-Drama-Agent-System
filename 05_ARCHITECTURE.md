# 05_ARCHITECTURE.md — AI Short Drama Production System

Status: Draft for review. Preconditions: EXPLORE_GATE = PASS and P0_SPIKE_GATE = CONDITIONAL_PASS. Scope is architecture only; no product implementation, migration, real provider, or production workflow is created.

## 1. System context

The system turns a creator brief into a reviewable 60–90 second vertical short drama through versioned planning, shot-level production, bounded repair, deterministic media render, review, and acceptance. Media, external jobs, costs, approvals, and evidence are auditable facts.

~~~mermaid
flowchart LR
  Creator --> Web["Next.js web"]
  Web --> API["FastAPI domain API"]
  API --> DB["PostgreSQL"]
  API --> Port["Orchestration port"]
  Port --> Engine["Workflow adapter: Temporal provisional"]
  Engine --> Provider["Mock or future provider adapters"]
  Engine --> Media["FFmpeg media worker"]
  Provider --> Storage["Storage adapter"]
  Media --> Storage
  DB --> Web
~~~

## 2. Container/component architecture

| Container | Owns | Does not own |
|---|---|---|
| Next.js web | creator commands, review and progress display | domain state or provider calls |
| FastAPI API | transport validation, application commands/queries | durable execution loops |
| PostgreSQL | business facts, constraints, ledgers and projections | workflow history or media bytes |
| orchestration adapter | durable execution through a port | business-policy decisions |
| Temporal worker | scheduling, waits, retries and signals | database truth or UI queries |
| media worker | FFmpeg render, probe and technical QC | story, approval or spend policy |
| provider adapter | external protocol mapping | direct domain mutation |
| storage adapter | immutable logical media keys | browser authorization policy |

## 3. Next.js / FastAPI boundary

Next.js is presentation and BFF only. FastAPI is the sole domain command boundary. Browser commands are short REST requests for creation, start confirmation, pause, resume, cancel, selection, impact approval, and issue resolution. FastAPI validates actor, version, budget and rights before invoking application services. Browser state is recovered from PostgreSQL and an event stream, never directly from Temporal. OpenAPI is the cross-runtime transport contract.

## 4. Domain/Application/Infrastructure layering

~~~mermaid
flowchart TB
  Domain["Domain: entities, policies, invariants"] --> App["Application: commands, queries, use cases"]
  App --> Ports["Ports: repository, orchestration, provider, storage, media, events"]
  Ports --> Infra["Adapters: PostgreSQL, Temporal, FFmpeg, storage, provider SDKs"]
  Transport["Next.js and FastAPI transport"] --> App
~~~

Domain defines Project, Shot, ShotVersion, DependencyEdge, Asset, Operation, ProviderAttempt, BudgetReservation, CostEvent, Issue, Review, TimelineVersion and EvidenceRecord. It imports no Temporal, ORM, HTTP, FFmpeg or cloud SDK types. Application services are the only authority for policy, state transition, budget and paid-submit decisions. Infrastructure implements ports and normalizes errors; it does not silently mutate domain state.

## 5. Orchestration abstraction

Application code invokes an orchestration port with stable IDs and immutable command payloads:

| Capability | Purpose |
|---|---|
| start_project_execution | start execution for a committed ProjectVersion |
| signal_execution | pause, resume, cancel, resolve, select or approve impact |
| reconcile_execution | re-drive incomplete persisted operations |
| execution_status | operations diagnostics, not domain truth |
| terminate_execution | controlled stop after domain cancellation |

The port allows a future workflow engine to replace Temporal without rewriting business rules, operation IDs, database facts, provider contracts, or API behavior.

## 6. Provisional Temporal integration

Temporal is a provisional adapter for durable waits, retry scheduling, fan-out/join and signals.

- Workflow code contains deterministic orchestration only.
- Database, storage, provider, FFmpeg, cost parsing and event publishing are activities or application services.
- Workflows pass domain IDs; they are not a second database.
- Temporal history is execution evidence, not the UI query model.
- Activity retry is at-least-once; business idempotency and reconciliation remain mandatory.
- Mock E2E on a supported long-lived Temporal deployment must prove worker replacement, pause/resume, replay and version evolution before this decision is confirmed.

## 7. Project Workflow

~~~mermaid
stateDiagram-v2
  [*] --> Preflight
  Preflight --> Planning
  Planning --> Bibles
  Bibles --> ShotPlan
  ShotPlan --> ProduceShots
  ProduceShots --> Assemble
  Assemble --> RoughCutReady
  RoughCutReady --> DeliverableRender
  DeliverableRender --> DeliverableReady
  DeliverableReady --> Accepted
  Preflight --> WaitingHuman
  ProduceShots --> WaitingHuman
  WaitingHuman --> ProduceShots
  Preflight --> Paused
  ProduceShots --> Paused
  Paused --> ProduceShots
  Preflight --> Cancelled
  ProduceShots --> Cancelled
~~~

The workflow coordinates a committed project version. Before a new paid operation it checks persisted pause and budget gates. Pausing blocks new paid work but continues reconciliation for jobs already submitted. Cancellation records intent and never assumes external cancellation succeeded.

## 8. Shot Workflow

The Shot workflow coordinates keyframe, candidates, technical QC, semantic/continuity QC, selection, bounded creative repair, and waiting-human. It may later be a child workflow or bounded activity sequence; that is a history/throughput decision. Only QC-driven creative repair consumes the two-repair limit. Transport retry, provider attempt, candidate generation and deterministic media retry remain separate counters.

## 9. Shot Graph versus Timeline

Timeline models playback order, clip offsets, captions, audio and transitions. The versioned Shot Graph models execution and invalidation. Edge types include EXECUTION_REQUIRES, DERIVED_FROM, CONTINUITY_REFERENCE, AUDIO_SYNC and INVALIDATES_ON_CHANGE.

Timeline order is not execution dependency. Continuity reference is not automatically blocking or invalidating. An approved edit computes an impact plan before versions are committed. Execution edges must be acyclic.

## 10. PostgreSQL responsibility

PostgreSQL is queryable business truth. It owns committed versions, state transitions, stable-operation uniqueness, Project/Shot/Asset/Issue/Review/Timeline projections, typed dependency edges, callback inbox deduplication, BudgetReservation, CostEvent, EventOutbox and EvidenceRecord metadata.

It does not own media bytes, unbounded logs, temporary signed URLs or workflow history. UI state is never reconstructed only from engine history.

## 11. Asset/Storage architecture

Assets have immutable logical keys:

    workspaces/{workspace}/projects/{project}/assets/{asset}/{version}/{filename}

The storage port uses local filesystem in development and can use S3 or OSS later. Write to a per-job scratch path, validate and probe, hash, atomically publish, then commit metadata and lineage. Selected and superseded are relational states; bytes are not overwritten. Browser access is controlled through API endpoints, not arbitrary filesystem paths.

## 12. Provider Adapter architecture

Adapters are capability-specific: image, video, TTS, lip-sync, music, moderation and vision review. Their descriptors declare input modes, limits, references, callback/polling, cancellation, idempotency, client lookup, region, restrictions, pricing and model version.

Application selects a route and repair policy. Adapters only map protocols, validate callbacks/downloads, normalize errors, query accepted jobs, and return attempt/cost facts. They never decide story or directly mutate Shot state.

## 13. Provider submission reconciliation

The required model is at-least-once execution plus business idempotency plus provider reconciliation:

1. Derive a stable operation ID from versioned intent and route.
2. Write Operation and BudgetReservation transactionally.
3. Submit with the same idempotency key or client reference when available.
4. Record SUBMISSION_UNKNOWN if acceptance may have occurred but response is absent.
5. Query by reference before any re-submit.
6. Escalate unresolved unknown submissions; never blind-retry a potentially paid operation.
7. Deduplicate callbacks in an inbox before application processing.

## 14. Budget reservation architecture

Before paid submission one transaction verifies:

    actual cost + active reservations + proposed upper bound <= approved budget

It creates one reservation keyed by operation. Only an authorized application command can settle, release or adjust it. A budget block prevents new paid work without erasing already accepted provider jobs.

## 15. CostEvent architecture

CostEvent is append-only: estimate, reservation, actual, adjustment, refund and failed-charge observation. Amounts use integer minor units, currency and pricing-version context. Records can identify project, scene, shot, operation, attempt and allocation rule. Project-level costs are not falsely assigned to one shot; views are projections, not mutable balances.

## 16. Evidence architecture

Evidence is an exportable derived index, not a duplicate of all logs/media. A record includes subject, type, logical URI, content hash, schema/tool/model version, timestamp, actor, correlation/causation IDs and verification outcome. It covers state transitions, versions, operations, attempts, cost/reservation changes, media hashes, ffprobe, QC, failure injection, recovery proof and final render hash. Credentials, headers and signed URLs are excluded or redacted.

## 17. Media Worker / FFmpeg architecture

Media workers run bounded CPU/disk jobs in isolated scratch directories. They take logical asset references and deterministic render specs, returning probes, hashes and output references. Evidence pins FFmpeg/ffprobe version, command snapshot, filters, fonts, timebase, encoder parameters and input hashes.

The first Mock performs full final MP4 re-render after approved replacement. It does not implement incremental segment cache. Technical QC checks 720x1280, 30fps, square pixels, duration, audio stream, subtitle render and container compatibility.

## 18. Progress/event delivery

Progress is a committed projection: current stage, completed/total shots, active jobs, failed/waiting-human items and actual/reserved spend. It does not fabricate linear percent or ETA.

FastAPI provides REST state recovery plus cursor-based SSE. EventOutbox records commit with domain transitions and allow replay after reconnect. Polling is an acceptable Mock fallback; WebSocket is not required.

## 19. Human takeover

Human takeover is limited to budget, rights/safety, irreducible creative ambiguity, provider hard failure, repair exhaustion and user-approved paid impact. Issues record owner, reason, evidence, allowed actions and lease/expiry. One Shot waiting-human does not pause independent Shots. All human commands use the same application validation and audit path.

## 20. Failure and recovery boundaries

| Boundary | Rule |
|---|---|
| API request | idempotent command key and persisted result |
| database | atomic transaction and outbox after commit |
| provider submit | operation ID, idempotency key, reconciliation first |
| callback | inbox deduplication then ordered application handling |
| worker loss | engine retries; application reuses operation and asset facts |
| media process | retry same deterministic inputs/tool version |
| storage publish | temporary write, probe/hash, atomic publish then metadata |
| engine | adapter resumes from IDs and persisted facts |

Temporal-specific worker-loss and version proof remains a Mock E2E gate.

## 21. Security boundaries

- FastAPI enforces authentication and authorization; Mock may use a fixed local actor/workspace without claiming production auth.
- Rights and consent are immutable facts before paid generation.
- Provider credentials remain server-side only.
- Uploads are size/type/hash validated; media parsing is isolated; path traversal and SSRF are blocked.
- Callbacks, replay windows, duplicate events and downloaded media are verified.
- Scratch, durable storage, database and browser boundaries are separate.

## 22. Local development topology

~~~mermaid
flowchart LR
  Web["Next.js dev"] --> API["FastAPI"]
  API --> PG["PostgreSQL"]
  API --> Port["Orchestration port"]
  Port --> Temporal["Temporal local: provisional"]
  Temporal --> Worker["Python worker"]
  Worker --> FF["FFmpeg worker"]
  Worker --> Mock["Mock providers"]
  FF --> FS["Local storage"]
~~~

## 23. Future production topology

Future production separates web/API, workflow workers and media workers for scale and fault isolation while retaining one modular domain codebase. PostgreSQL becomes highly available business storage; object storage replaces local storage; managed or supported long-lived workflow infrastructure is evaluated before adoption. This document selects no cloud, Kubernetes, workflow deployment mode, real provider, storage vendor or auth vendor.

## 24. Explicit non-goals

- no application code, migrations, production workflows, provider integrations or UI implementation;
- no microservice-per-agent design, LoRA training, local GPU cluster or Kubernetes;
- no full SaaS auth/billing/collaboration, incremental render cache, required WebSocket, project copy or long-form production;
- no claim that local Temporal evidence proves production durability/versioning.

## 25. Architecture invariants

1. PostgreSQL stores approved, versioned, auditable business truth.
2. Domain/application code has no Temporal implementation dependency.
3. Application services alone authorize state, budget and paid submission.
4. Each paid logical action has one stable operation ID and reconciliation path.
5. Unknown external acceptance is never blindly resubmitted.
6. Published asset bytes are immutable and lineage is explicit.
7. Timeline and Shot Graph remain separate.
8. Only creative/QC repair consumes the two-repair budget.
9. Progress comes from committed facts, not engine history.
10. Evidence records meaningful transitions without secrets.
11. Pause blocks new paid work while submitted work reconciles.
12. Provider and workflow-engine adapters are replaceable.

## 26. Provisional decisions and future gates

| Decision | Status | Gate |
|---|---|---|
| modular monolith with process separation | proposed baseline | architecture review |
| PostgreSQL business truth and append-only ledgers | P0-supported | data-contract review |
| typed Shot Graph separate from Timeline | SPIKE-05-supported | graph schema review |
| atomic BudgetReservation | SPIKE-04-supported | PostgreSQL implementation test |
| stable operation/reconciliation | SPIKE-03-supported | provider contract test |
| deterministic full FFmpeg re-render | SPIKE-06-supported | Mock E2E media test |
| Temporal orchestration adapter | provisional | Mock E2E on supported long-lived deployment proves recovery, pause/resume, replay and version evolution |
| child workflow versus activity topology | undecided | history/throughput benchmark |
| SSE versus polling default | P1 | Mock UX integration |
| real providers, storage, auth and deployment | deferred | later specifications |

## Gate

ARCHITECTURE_GATE = READY_FOR_REVIEW

This means boundaries, invariants and provisional decisions are ready for review. It does not approve implementation or close the Mock E2E Temporal gate.
