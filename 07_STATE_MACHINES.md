# 07_STATE_MACHINES.md — Canonical State Machines

Status: Draft for Product Owner review. This document is coupled to `06_DATA_CONTRACTS.md`. State names are domain contracts, not ORM enums or workflow-engine implementation types.

## 1. State-machine rules

1. There is no giant status enum. Project phase, execution gate, health, Shot, Job, Operation, ProviderAttempt, Asset, Issue, Review, and BudgetReservation are independent machines.
2. Application/Domain Service is the sole command path that validates and records domain transitions. Other authorities submit facts or authorized commands; they do not write domain rows directly.
3. Every transition records from/to state, event/command ID, Actor, authority type, reason, occurred/recorded time, correlation ID, causation ID, expected row version, and resulting row version.
4. Repeated delivery of the same command/event is idempotent and returns the recorded result.
5. Illegal transitions fail closed and create diagnostics/Evidence; they are never coerced to a nearby state.
6. Workflow/Temporal state is scheduling state, not a duplicate domain state machine.

### 1.1 Authorities

| Authority | May do |
|---|---|
| Domain/Application Service | validate commands/facts, enforce invariants, perform every persisted domain transition |
| Orchestration Adapter | request scheduling transitions and report durable execution facts through application commands |
| Provider Adapter | report normalized provider submission/status/cancellation facts only |
| Media Worker | report deterministic media/QC facts only |
| QC subsystem | submit versioned Review findings and repair recommendations |
| Human / Product Owner | issue application commands allowed by role, including pause, cancel, selection, issue resolution, risk acceptance, budget approval, deliverable acceptance |
| System reconciliation job | query persisted/external facts and submit reconciliation commands; cannot invent provider success or spend |

Whenever a table lists a non-application authority, the transition is still executed by the Domain/Application Service after authorization and invariant checks.

## 2. Project lifecycle

Project lifecycle expresses durable production phase only. It does not encode pause, local issues, provider polling, budget holds, or UI health.

```text
DRAFT → PREFLIGHT → READY → RUNNING → ROUGH_CUT_READY
                                      → DELIVERABLE_READY → ACCEPTED

Any nonterminal phase → CANCELLED
RUNNING/ROUGH_CUT_READY/DELIVERABLE_READY → FAILED (project-wide terminal failure only)
```

`PUBLISHED` is not an MVP production lifecycle state. `COMPLETED` in older specifications is replaced by the approved distinction between `DELIVERABLE_READY` and human `ACCEPTED`.

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | create project | `DRAFT` | Human through Application Service | create Project and draft ProjectVersion; no paid work |
| `DRAFT` | start confirmed; brief/version committed | `PREFLIGHT` | Human / Product Owner | record rights/budget confirmation and preflight command |
| `PREFLIGHT` | all mandatory preflight Reviews pass | `READY` | Domain/Application Service | persist pass evidence; no unresolved project-wide gate |
| `PREFLIGHT` | correctable blocker found | `PREFLIGHT` | Domain/Application Service | open Issue and/or global gate; lifecycle does not become waiting-human |
| `READY` | execution accepted and no global gate | `RUNNING` | Orchestration Adapter request | start/attach orchestration execution by committed ProjectVersion |
| `RUNNING` | all required usable Shots/assets assembled; rough-cut technical Review passes | `ROUGH_CUT_READY` | Domain/Application Service after Media Worker/QC facts | select TimelineVersion and rough-cut asset/evidence |
| `ROUGH_CUT_READY` | final render requested and final technical/packaging Reviews pass | `DELIVERABLE_READY` | Human command then Domain/Application Service after Media Worker/QC facts | record immutable deliverable assets, manifest, cost/evidence reports |
| `DELIVERABLE_READY` | creator accepts exact deliverable version | `ACCEPTED` | Human / Product Owner | immutable acceptance Review and accepted Timeline/AssetVersion refs |
| `ROUGH_CUT_READY` | approved edits/repairs require production | `RUNNING` | Human / Product Owner | commit Impact Plan and new versions; old rough cut retained |
| `DELIVERABLE_READY` | change requested | `RUNNING` or `ROUGH_CUT_READY` | Human / Product Owner | new version/Impact Plan; accepted state not yet reached |
| any nonterminal | user cancellation intent validated | `CANCELLED` | Human / Product Owner | set global cancellation gate, propagate cancel requests, retain bytes/cost/evidence |
| `RUNNING`, `ROUGH_CUT_READY`, `DELIVERABLE_READY` | explicit project-wide unrecoverable decision after Issue resolution | `FAILED` | Human / Product Owner or Domain Service under approved policy | terminal reason/evidence; no inference from one Shot failure |

`ACCEPTED`, `CANCELLED`, and `FAILED` are terminal for that ProjectVersion production run. Further creative work requires a new ProjectVersion/run; prior acceptance remains auditable.

## 3. Project execution gates and health projection

### 3.1 Execution gate

Execution gating is a set of persisted reasons, not a Project lifecycle state. The derived gate is `OPEN` when no active reason prohibits new paid work and `CLOSED` otherwise.

| Gate reason | Scope | Opened by | Cleared by | Effect |
|---|---|---|---|---|
| `BUDGET_EXHAUSTED` | project-wide | Application Service after atomic reservation denial | Human budget approval or approved lower-cost Impact Plan | stop new paid Operations |
| `SAFETY_RIGHTS` | project-wide where unresolved rights/safety affects lawful execution | Application Service/QC/moderation fact | authorized Human resolution plus validation | stop affected and, when project-wide, all new paid Operations |
| `CREATIVE_DECISION_REQUIRED` | project-wide only when unavoidable choice blocks meaningful continuation | Domain creative policy/QC | Human choice command | stop new paid Operations that would assume the choice |
| `PROVIDER_WIDE_UNRECOVERABLE` | project-wide capability outage with no approved equivalent route | Application Service from provider/reconciliation facts | provider recovery or Human-approved route change | stop new affected paid Operations; unrelated capabilities continue if gate scope permits |
| `USER_PAUSED` | project-wide | Human pause command | Human resume after persisted preflight checks | stop all new paid Operations |
| `USER_CANCELLED` | project-wide terminal intent | Human cancel command | never cleared for this run | stop new work; request cancellation where supported |

Rules:

- A Shot failure, repair exhaustion, or Shot-level `WAITING_HUMAN` Issue is never a global gate.
- Gates prohibit **new paid submission**. Accepted provider work continues status polling/callback processing, reconciliation, download/validation, CostEvent recording, and safe metadata finalization.
- Free deterministic work may continue when it cannot violate the gate reason. For `USER_CANCELLED`, only reconciliation, cleanup, evidence, and cost finalization continue.
- Opening/clearing a gate is an audited application command; infrastructure cannot toggle it directly.
- Resume rechecks provider availability, budget, rights, version compatibility, and dependencies from persisted facts.

### 3.2 Derived health

Health is rebuildable UI projection, not durable lifecycle:

| Health | Derivation example |
|---|---|
| `HEALTHY` | active lifecycle with no open warning/error Issues and gate open |
| `RUNNING_WITH_ISSUES` | lifecycle `RUNNING`; one or more local Issues; independent work can proceed |
| `GLOBALLY_BLOCKED` | at least one active project-wide execution gate |
| `RECOVERING` | reconciliation jobs active for unknown/submitted operations after interruption |
| `DEGRADED` | approved fallback/accepted risk in use |
| `TERMINAL` | lifecycle `ACCEPTED`, `CANCELLED`, or `FAILED` |

Multiple conditions may exist; API returns primary health plus reasons rather than persisting one lossy enum.

## 4. Shot lifecycle

```text
PLANNED → KEYFRAME_IN_PROGRESS → KEYFRAME_READY
        → CANDIDATE_GENERATING → CANDIDATES_READY → QC_IN_PROGRESS
        → APPROVED

QC_IN_PROGRESS → REPAIR_PLANNED → CANDIDATE_GENERATING
QC_IN_PROGRESS/REPAIR_PLANNED → WAITING_HUMAN
WAITING_HUMAN → REPAIR_PLANNED | APPROVED | REJECTED | CANCELLED
Any usable state → INVALIDATED → PLANNED/REPAIR_PLANNED
Committed replacement → SUPERSEDED
Nonterminal → CANCELLED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | committed ShotVersion/ShotSpec created | `PLANNED` | Domain/Application Service | record graph/version refs |
| `PLANNED` | keyframe operation authorized | `KEYFRAME_IN_PROGRESS` | Orchestration Adapter request | dependencies/gates/budget checked |
| `KEYFRAME_IN_PROGRESS` | validated keyframe AssetVersion selected | `KEYFRAME_READY` | Application Service after Provider/Media/QC facts | lineage and selection recorded |
| `PLANNED`, `KEYFRAME_READY`, `REPAIR_PLANNED` | candidate operations authorized | `CANDIDATE_GENERATING` | Orchestration Adapter request | exact strategy and candidate slots fixed |
| `CANDIDATE_GENERATING` | required candidate set reaches usable terminal facts | `CANDIDATES_READY` | Domain/Application Service | failed optional candidates may coexist |
| `CANDIDATES_READY` | versioned QC requested | `QC_IN_PROGRESS` | Orchestration Adapter/QC subsystem | bind exact candidates/criteria versions |
| `QC_IN_PROGRESS` | passing Review and selected candidate | `APPROVED` | Domain/Application Service; Human if policy requires selection | selection, Review, lineage audit |
| `QC_IN_PROGRESS` | QC fails; strategy-changing repair allowed and count < 2 | `REPAIR_PLANNED` | QC recommendation accepted by Domain/Application Service | increment persistent repair count once; commit Repair Plan |
| `QC_IN_PROGRESS`, `REPAIR_PLANNED` | repair exhausted, ambiguity, or local human action required | `WAITING_HUMAN` | Domain/Application Service | open/dedupe local Issue; independent Shots continue |
| `WAITING_HUMAN` | human approves a changed repair strategy and budget | `REPAIR_PLANNED` | Human / Product Owner | normal command, new ShotVersion/Operation as needed; no counter reset |
| `WAITING_HUMAN` | human selects acceptable existing candidate/accepts risk with valid Review policy | `APPROVED` | Human / Product Owner | resolution and acceptance Review/evidence |
| `WAITING_HUMAN` | human rejects Shot | `REJECTED` | Human / Product Owner | Issue resolved; downstream Impact Plan |
| `APPROVED`, `KEYFRAME_READY`, `CANDIDATES_READY`, `WAITING_HUMAN` | approved source change impact marks version unusable | `INVALIDATED` | Domain/Application Service | Impact Plan and new version; bytes retained |
| `INVALIDATED` | new ShotVersion committed | `PLANNED` or `REPAIR_PLANNED` | Domain/Application Service | choice depends on whether change is repair or creator edit |
| any nonterminal | local cancellation intent | `CANCELLED` | Human / Product Owner or parent cancellation policy | cancel unstarted work; reconcile accepted work |
| any nonterminal/approved version | newer ShotVersion becomes current replacement | `SUPERSEDED` | Domain/Application Service | historical selections/bytes remain |

`REJECTED`, `CANCELLED`, and `SUPERSEDED` are terminal for the ShotVersion. `FAILED` is intentionally not a final Shot state: failures are Operation/Job facts that lead to repair, Issue, rejection, or cancellation.

## 5. Job lifecycle

Jobs are internal schedulable work and do not represent external provider truth.

```text
QUEUED → CLAIMED → RUNNING → SUCCEEDED
                    ↘ RETRY_SCHEDULED → QUEUED
                    ↘ FAILED
QUEUED/CLAIMED/RUNNING → CANCEL_REQUESTED → CANCELLED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | application enqueues immutable payload | `QUEUED` | Domain/Application Service / Orchestration Adapter | idempotency key and payload version persisted |
| `QUEUED` | worker obtains execution lease | `CLAIMED` | Orchestration Adapter/Media Worker runtime | worker lease only; no human Issue lease semantics |
| `CLAIMED` | handler starts | `RUNNING` | Orchestration Adapter/Media Worker | execution ID/heartbeat facts |
| `RUNNING` | valid result persisted | `SUCCEEDED` | Application Service after worker fact | result hash/evidence; downstream command |
| `RUNNING`, `CLAIMED` | recoverable technical/transport failure within job policy | `RETRY_SCHEDULED` | Orchestration Adapter | increment correct retry counter, not repair count |
| `RETRY_SCHEDULED` | backoff elapsed and gate policy permits | `QUEUED` | Orchestration Adapter | same Job and Operation IDs |
| `RUNNING`, `CLAIMED` | nonrecoverable/exhausted job failure | `FAILED` | Application Service after worker fact | normalized error/evidence; does not directly fail Shot/Project |
| `QUEUED`, `CLAIMED`, `RUNNING`, `RETRY_SCHEDULED` | cancellation intent | `CANCEL_REQUESTED` | Human/Application Service or parent cancellation policy | send cooperative cancel where supported |
| `CANCEL_REQUESTED` | work not started or worker confirms stop | `CANCELLED` | Application Service after runtime fact | retain partial/evidence per policy |
| `CANCEL_REQUESTED` | completion wins race | `SUCCEEDED` or `FAILED` | Application Service after fact | cancellation intent retained; actual result/cost honored |

## 6. Operation lifecycle

An Operation is one logical side effect. These states are authoritative for paid-idempotency behavior.

```text
PLANNED → RESERVED → SUBMITTING → SUBMITTED → SUCCEEDED
                         ↘ SUBMISSION_UNKNOWN → RECONCILING → SUBMITTED | SUCCEEDED | FAILED
SUBMITTED → RECONCILING → SUBMITTED | SUCCEEDED | FAILED
PLANNED/RESERVED/SUBMITTING/SUBMITTED/SUBMISSION_UNKNOWN/RECONCILING
  → CANCEL_REQUESTED → CANCELLED | SUCCEEDED | FAILED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | stable logical intent accepted | `PLANNED` | Domain/Application Service | deterministic Operation ID and intent hash |
| `PLANNED` | atomic upper-bound reservation succeeds | `RESERVED` | Domain/Application Service | link active BudgetReservation; paid operations only |
| `PLANNED` | operation is provably free/no reservation required | `RESERVED` | Domain/Application Service | record zero/no-charge policy evidence |
| `RESERVED` | submit command begins; gate still open | `SUBMITTING` | Orchestration Adapter request | same stable client reference/idempotency key |
| `SUBMITTING` | provider acceptance and external job ID known | `SUBMITTED` | Provider Adapter fact via Application Service | create/update ProviderAttempt; retain reservation |
| `SUBMITTING` | response lost/ambiguous after request may have reached provider | `SUBMISSION_UNKNOWN` | Provider Adapter/transport fact via Application Service | prohibit automatic new paid submit; schedule reconciliation |
| `SUBMISSION_UNKNOWN`, `SUBMITTED` | lookup/poll/callback reconciliation starts | `RECONCILING` | System reconciliation job | query by client ref/external ID; no blind submit |
| `RECONCILING` | provider confirms accepted/running | `SUBMITTED` | Provider Adapter fact | record observation and external job ID |
| `SUBMITTED`, `RECONCILING` | provider result validated and immutable output finalized | `SUCCEEDED` | Application Service after Provider/Storage/QC facts | settle reservation, CostEvents, assets/lineage/evidence |
| `SUBMITTED`, `RECONCILING` | provider confirms terminal failure/no usable result | `FAILED` | Application Service | settle/release as real billing facts require |
| `RECONCILING` | provider proves no submission exists and policy authorizes retry | `RESERVED` | Domain/Application Service | same Operation ID; new ProviderAttempt allowed; explicit proof recorded |
| `SUBMISSION_UNKNOWN`, `RECONCILING` | uncertainty cannot be resolved within policy | `FAILED` | Human / Product Owner or approved application policy | Issue/evidence; never automatically create new paid Operation |
| any nonterminal | cancellation intent validated | `CANCEL_REQUESTED` | Human/Application Service or parent cancellation | ask provider when supported; retain facts |
| `CANCEL_REQUESTED` | provider confirms cancellation or no submit occurred | `CANCELLED` | Application Service after Provider/reconciliation fact | settle/release from actual billing facts |
| `CANCEL_REQUESTED` | provider completes or fails despite intent | `SUCCEEDED` or `FAILED` | Application Service after fact | retain cancellation intent and charge/result evidence |

Direct `SUBMISSION_UNKNOWN → SUBMITTING` is forbidden. Transport retry before any bytes could have reached the provider may remain within the same `SUBMITTING` ProviderAttempt only when the adapter can prove no acceptance risk; otherwise it becomes unknown.

## 7. ProviderAttempt lifecycle

```text
CREATED → REQUESTING → ACCEPTED → RUNNING → SUCCEEDED | FAILED
                    ↘ ACCEPTANCE_UNKNOWN → RECONCILING → ACCEPTED | RUNNING | SUCCEEDED | FAILED | NOT_FOUND
ACCEPTED/RUNNING → CANCEL_REQUESTED → CANCELLED | SUCCEEDED | FAILED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | provider interaction allocated for Operation | `CREATED` | Domain/Application Service | immutable provider/request mapping version/client ref |
| `CREATED` | adapter starts request | `REQUESTING` | Provider Adapter | request hash and transport execution fact |
| `REQUESTING` | acceptance response verified | `ACCEPTED` | Provider Adapter fact | external job ID/reference |
| `REQUESTING` | acceptance ambiguous | `ACCEPTANCE_UNKNOWN` | Provider Adapter fact | cause Operation `SUBMISSION_UNKNOWN` |
| `ACCEPTED` | provider reports work active | `RUNNING` | Provider Adapter callback/poll fact | provider sequence/time retained |
| `ACCEPTANCE_UNKNOWN`, `ACCEPTED`, `RUNNING` | lookup begins | `RECONCILING` | System reconciliation job | use client ref/external ID |
| `RECONCILING` | accepted/running fact | `ACCEPTED` or `RUNNING` | Provider Adapter fact | ordered observation |
| `RECONCILING` | provider proves no matching job | `NOT_FOUND` | Provider Adapter fact | proof/evidence; Operation policy decides reuse/resubmit |
| `ACCEPTED`, `RUNNING`, `RECONCILING` | result response/callback verified | `SUCCEEDED` | Provider Adapter fact then Application Service | result references; Operation waits for validation/publish |
| any active state | terminal provider error verified | `FAILED` | Provider Adapter fact then Application Service | normalized error/billing observation |
| `ACCEPTED`, `RUNNING` | cancellation sent | `CANCEL_REQUESTED` | Provider Adapter after application command | provider request/ref retained |
| `CANCEL_REQUESTED` | provider confirms cancellation | `CANCELLED` | Provider Adapter fact | not assumed from HTTP send alone |
| `CANCEL_REQUESTED` | terminal completion/failure wins race | `SUCCEEDED` or `FAILED` | Provider Adapter fact | actual result/cost retained |

`NOT_FOUND` is not permission by itself to create a new logical Operation. Application policy evaluates proof strength and keeps the same Operation ID.

## 8. Asset lifecycle

Asset byte publication and selection are separate dimensions. Canonical byte lifecycle:

```text
TEMPORARY → VALIDATING → VALIDATED → PUBLISHING → PUBLISHED
TEMPORARY/VALIDATING → REJECTED
PUBLISHED → QUARANTINED
PUBLISHED/QUARANTINED → DELETE_PENDING → DELETED_TOMBSTONE
```

Selection disposition for a published AssetVersion is independently `UNSELECTED`, `SELECTED`, or `SUPERSEDED`.

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | isolated temporary write opened | `TEMPORARY` | Storage Adapter after application-authorized Job | temporary handle/expiry; not domain-visible as usable |
| `TEMPORARY` | writer closes successfully | `VALIDATING` | Media Worker/Provider Adapter fact | probe/hash/virus/type validation requested |
| `VALIDATING` | all required checks pass | `VALIDATED` | Application Service after Media Worker/security facts | hash/probe Evidence |
| `VALIDATING`, `TEMPORARY` | checks/write fail | `REJECTED` | Application Service | reason/evidence; scratch cleanup eligible |
| `VALIDATED` | immutable publish starts | `PUBLISHING` | Storage Adapter after application command | content-addressed/logical key fixed |
| `PUBLISHING` | storage confirms immutable object | `PUBLISHED` | Application Service after Storage fact | metadata, lineage, evidence, outbox finalize transactionally |
| `PUBLISHING` | ambiguous storage result | `PUBLISHING` | System reconciliation job | head/hash reconcile; never advertise until confirmed |
| `PUBLISHED` | rights/security/integrity issue | `QUARANTINED` | Application Service from authorized review/security fact | remove from new selections; retained for audit |
| `PUBLISHED`, `QUARANTINED` | deletion requested and retention/reference checks start | `DELETE_PENDING` | Human/Application Service under retention policy | tombstone plan; no immediate history rewrite |
| `DELETE_PENDING` | no retained references/legal hold and physical removal confirmed | `DELETED_TOMBSTONE` | Storage Adapter fact via Application Service | retain metadata/hash/lineage/cost/evidence tombstone |

Selection transitions:

- `UNSELECTED → SELECTED`: Human or approved automatic selection command with passing Review.
- `SELECTED → SUPERSEDED`: new AssetVersion/TimelineVersion selected or invalidation approved.
- `SUPERSEDED → SELECTED`: explicit rollback/new TimelineVersion; original bytes remain.

Filesystem rename is never a state transition or domain prerequisite.

## 9. Issue lifecycle

MVP Issue semantics deliberately omit lease and expiry.

```text
OPEN → AUTO_REPAIRING → RESOLVED
OPEN/AUTO_REPAIRING → WAITING_HUMAN
WAITING_HUMAN → RESOLVED | ACCEPTED_RISK | CANCELLED
OPEN → CANCELLED (duplicate/no longer applicable, with reason)
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | actionable finding deduped | `OPEN` | Domain/Application Service from QC/provider/budget/security fact | reason, issue type, affected entity, allowed actions |
| `OPEN` | bounded automatic repair authorized | `AUTO_REPAIRING` | Domain/Application Service | link Repair Plan/Operation; increment repair count only for creative repair |
| `AUTO_REPAIRING` | validation confirms problem fixed | `RESOLVED` | Domain/Application Service after QC Review | resolution, resolver actor/subsystem, time/evidence |
| `OPEN`, `AUTO_REPAIRING` | repair unavailable/exhausted or decision needed | `WAITING_HUMAN` | Domain/Application Service | local/global scope explicit; no automatic Project lifecycle mutation |
| `WAITING_HUMAN` | human command solves issue and validation passes where required | `RESOLVED` | Human / Product Owner | audited normal application command and resulting versions |
| `WAITING_HUMAN` | policy permits risk acceptance | `ACCEPTED_RISK` | Human / Product Owner with required role | exact risk/evidence/scope; may derive degraded health |
| `WAITING_HUMAN`, `OPEN` | affected work cancelled or duplicate/obsolete issue closed | `CANCELLED` | Human/Product Owner or Domain Service for proven duplicate | resolution reason; never delete history |

A Shot-scoped `WAITING_HUMAN` Issue leaves Project lifecycle `RUNNING` and health `RUNNING_WITH_ISSUES`. Only an Issue whose type and affected scope match the approved global-gate list may open a project execution gate.

## 10. Review lifecycle

```text
REQUESTED → RUNNING → PASSED | FAILED | NEEDS_HUMAN
NEEDS_HUMAN → PASSED | FAILED | ACCEPTED_RISK | CANCELLED
REQUESTED/RUNNING → CANCELLED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | exact subject/criteria versions submitted | `REQUESTED` | Domain/Application Service/Orchestration Adapter | immutable Review input hash |
| `REQUESTED` | reviewer starts | `RUNNING` | QC subsystem or Human through Application Service | reviewer/tool/model version |
| `RUNNING` | criteria pass with actionable findings recorded | `PASSED` | QC subsystem fact; Human for final acceptance Review | immutable result/evidence |
| `RUNNING` | criteria fail conclusively | `FAILED` | QC subsystem/Human fact | issue codes and repair actions; may open Issue |
| `RUNNING` | ambiguity/policy requires human judgment | `NEEDS_HUMAN` | QC subsystem/Domain Service | allowed actions and Issue link |
| `NEEDS_HUMAN` | human approves exact subject | `PASSED` | Human / Product Owner | identity, scope, evidence |
| `NEEDS_HUMAN` | human rejects | `FAILED` | Human / Product Owner | reasons/Impact Plan as needed |
| `NEEDS_HUMAN` | policy permits explicit risk acceptance | `ACCEPTED_RISK` | Human / Product Owner | risk statement; cannot bypass rights/safety prohibitions |
| `REQUESTED`, `RUNNING`, `NEEDS_HUMAN` | subject superseded/cancelled | `CANCELLED` | Domain/Application Service | retain partial findings; new subject requires new Review |

Rerun creates a new Review. A previous pass does not automatically apply to changed bytes or versioned intent.

## 11. BudgetReservation lifecycle

```text
REQUESTED → ACTIVE → SETTLING → SETTLED
                   ↘ RELEASING → RELEASED
ACTIVE/SETTLING → ADJUSTMENT_REQUIRED → SETTLED | RELEASED
REQUESTED → REJECTED
```

| From | Event / guard | To | Initiating authority | Required effects |
|---|---|---|---|---|
| — | paid Operation requests upper bound | `REQUESTED` | Domain/Application Service | Money/currency/pricing context/Operation fixed |
| `REQUESTED` | serialized capacity check passes | `ACTIVE` | Domain/Application Service in one DB transaction | reservation and outbox/audit commit atomically |
| `REQUESTED` | capacity check fails | `REJECTED` | Domain/Application Service | budget Issue/global gate; no provider submission |
| `ACTIVE` | terminal/partial provider billing facts available | `SETTLING` | Domain/Application Service / reconciliation command | CostEvents prepared from actual facts |
| `SETTLING` | actual/adjustment events committed | `SETTLED` | Domain/Application Service | held amount released; actual ledger retained |
| `ACTIVE` | proven no charge/no submission and operation terminal | `RELEASING` | Domain/Application Service | reason/evidence |
| `RELEASING` | release committed | `RELEASED` | Domain/Application Service | capacity projection updated |
| `ACTIVE`, `SETTLING` | charge uncertain, exceeds hold, refund/adjustment pending | `ADJUSTMENT_REQUIRED` | System reconciliation job/Application Service | Issue/evidence; no fabricated balance |
| `ADJUSTMENT_REQUIRED` | authoritative billing facts resolved | `SETTLED` or `RELEASED` | Domain/Application Service | append actual/adjustment/refund CostEvents |

Reservations do not expire automatically in MVP. A reconciliation policy may flag stale reservations for investigation, but release requires authoritative Operation/provider facts.

## 12. Retry and attempt taxonomy

| Concept | Identity/counter | Typical trigger | Creates new Operation? | Consumes `max_repair_cycles=2`? |
|---|---|---|---:|---:|
| Transport Retry | same Job/ProviderAttempt transport counter | timeout, 429, recoverable 5xx where acceptance risk is handled | no | no |
| Provider Attempt | new `provider_attempt_id` under same Operation | deliberate provider interaction/reconciliation-resubmit after proof | no | no |
| Candidate Generation | distinct candidate slot/purpose and Operation | intentional creative alternatives | yes | no |
| Deterministic Media Retry | same render Operation/Job retry counter and identical spec | worker crash, transient FFmpeg/I/O failure | no | no |
| Creative Repair Cycle | persistent Shot repair counter plus new strategy/input Operation | QC failure changes prompt/reference/route/action to fix content | yes | **yes** |

Rules preventing repair-budget loopholes:

- count is stored on the stable Shot aggregate and linked Repair Plan, not Job/Operation IDs;
- increment occurs once when a strategy-changing repair is authorized, before its Operations start;
- replay/idempotent command returns the same increment result;
- splitting repair into multiple provider/media operations still consumes one cycle;
- candidate generation before QC failure is not mislabeled repair; additional candidates after QC failure intended to fix findings are repair-cycle outputs;
- user regeneration after failure is classified by intent: a repair consumes a cycle; a creator-requested alternative after explicit takeover is audited as human-directed regeneration and cannot silently restore automatic repair allowance.

## 13. Cooperative pause and resume

Pause is the `USER_PAUSED` global gate, not a Project lifecycle phase.

On pause:

- no new paid Operation may enter `SUBMITTING`;
- queued free work may continue only if policy says safe;
- accepted/unknown provider work continues callbacks, polling, reconciliation, download, validation, cost settlement, and evidence;
- completed assets remain valid;
- cancellation is not assumed or automatically substituted for pause.

On resume, Application Service clears the gate only after persisted provider, budget, rights, schema compatibility, dependency, and cancellation checks pass. Orchestration continues from Project/Shot/Operation facts and does not restart completed work.

## 14. Cancellation semantics

Cancellation intent and external cancellation success are separate facts.

- User Project/Shot cancel sets domain intent/gate and drives `CANCEL_REQUESTED` on relevant Jobs/Operations/ProviderAttempts.
- A successful request transmission does not mean the provider cancelled; only verified provider state reaches ProviderAttempt `CANCELLED`.
- Completion can win the race. Resulting AssetVersions, CostEvents, and Evidence are retained even if not selected.
- No cancellation deletes prior CostEvents, reservations, callbacks, evidence, lineage, Reviews, or published bytes.
- Storage deletion is a later retention-authorized Asset transition, never an automatic cancellation side effect.

## 15. Invalidation and supersession

All changes use the `ImpactPlan` contract in `06_DATA_CONTRACTS.md` and the graph version current at planning time.

| Change | Minimum impact behavior |
|---|---|
| Dialogue version | invalidate/review bound TTS, subtitle, lip-sync, timing-dependent video, and affected Timeline render; unrelated Shots remain |
| CharacterLook version | traverse explicit derived/invalidation edges for consuming ShotVersions/assets; continuity references alone flag review unless policy says invalidate |
| Keyframe selection/version | invalidate image-to-video/first-last-frame descendants tied to exact keyframe; retain other candidates |
| Selected candidate | create new Shot/Timeline selection facts and TimelineVersion; rerun relevant technical QC/render; no provider regeneration unless required |
| Scene/Location version | impact only ShotVersions referencing changed exact fields/versions through declared edges |
| Prop state/version | impact Shots/assets that consume that state; later chronological playback alone is not proof of dependency |

An invalidated/superseded version is not deleted. Its bytes, lineage, reviews, costs, operations, and evidence remain queryable. New work uses new immutable version IDs and stable operation semantics.

## 16. Human takeover

Human actions use normal authenticated application commands with expected versions, allowed-action validation, impact/cost preview, and Evidence. No administrator or UI writes statuses directly.

Minimum flow:

```text
Issue OPEN → AUTO_REPAIRING (when bounded repair is available)
          → WAITING_HUMAN (when repair is unavailable/exhausted or judgment is required)
          → RESOLVED | ACCEPTED_RISK | CANCELLED
```

Allowed human commands may select an existing candidate, approve a new repair strategy/cost, provide/replace authorized input, edit versioned content, accept permitted risk, reject/cancel a Shot, increase budget, change route, resume, or accept a deliverable. Each command produces ordinary versions, Reviews, Operations, transition records, and outbox events.

## 17. Cross-machine constraints

1. ProviderAttempt `SUCCEEDED` does not make Operation `SUCCEEDED` until output validation and immutable publish complete.
2. Operation/Job `FAILED` does not directly make Shot or Project `FAILED`.
3. Shot `WAITING_HUMAN` does not alter Project lifecycle or create a gate unless a separate approved project-wide Issue exists.
4. Project `ROUGH_CUT_READY` requires all required Timeline clips reference usable selected AssetVersions; accepted-risk omissions are explicit.
5. Project `DELIVERABLE_READY` requires final technical Review pass and immutable deliverable/evidence package.
6. Project `ACCEPTED` requires a Human/Product Owner Review of the exact deliverable version.
7. Asset `PUBLISHED` precedes its use in a TimelineVersion or successful Operation result.
8. Operation cannot enter `SUBMITTING` without an active reservation (or recorded free-operation exemption) and open execution gate.
9. BudgetReservation terminal state and CostEvent ledger must reconcile, including cancellation races/refunds.
10. Unsupported schema/workflow payload versions open an Issue/gate as scoped; they are not silently interpreted.

## 18. Cross-document consistency review

Reviewed inputs: `INTENT.md`, `02_DECISIONS.md`, `03_PRODUCT_SPEC.md`, `04_USER_FLOWS.md`, `EXPLORE_REPORT.md`, `SPIKE_EVIDENCE.md`, and `05_ARCHITECTURE.md`.

| Check | Result | Resolution in these drafts |
|---|---|---|
| status naming | older `COMPLETED` and project-wide `WAITING_USER` conflict with later approved clarification | canonical completion is `ROUGH_CUT_READY → DELIVERABLE_READY → ACCEPTED`; waiting is Issue/gate, not lifecycle |
| duplicate sources of truth | architecture warns against workflow/UI truth | PostgreSQL aggregates/ledgers authoritative; workflow and health/progress are execution/projections |
| impossible transitions | older flows conflate pause/cancel with external state | cooperative gate and cancellation-intent race transitions are explicit |
| versioning gaps | old payload interpretability unspecified | per-payload schema/contract version plus unsupported/migrator policy |
| duplicate paid operations | response-loss risk confirmed by SPIKE-03 | stable Operation, unknown/reconcile states, same client ref, no blind submit |
| global blocking | older `WAITING_USER` examples can imply whole-project block for Shot issue | local Issue keeps independent Shots running; only enumerated project gates block paid work |
| Shot Graph / Timeline | older “sequence dependency” wording can be confused with playback | typed graph and Timeline explicitly separate |
| Asset overwrite | local filesystem language could imply rename contract/overwrite | Storage publish abstraction and immutable AssetVersions; rename only possible local technique |
| repair budget | older job/task wording leaves loopholes | five counters separated; Shot-level persistent creative repair count only |
| audit/evidence | minimum facts previously scattered | common transition audit, lineage, inbox/outbox, costs, Reviews, Evidence contracts centralized |

### 18.1 Contradictions found

Two vocabulary contradictions exist in older approved product/flow text:

1. `03_PRODUCT_SPEC.md` and `04_USER_FLOWS.md` end the project at `COMPLETED`; the later Product Owner clarification in `EXPLORE_REPORT.md` and the present architecture review requires `DELIVERABLE_READY → ACCEPTED`.
2. Older flows use project `WAITING_USER` for both budget/global blockers and local Shot takeover; the approved architecture note requires local Shot Issues not to globally block independent work.

These drafts treat the later explicit Product Owner clarifications as authoritative and do not modify the older files. No contradiction was found that requires choosing between `INTENT.md` and `02_DECISIONS.md`.

### 18.2 Unresolved Product Owner decisions

None required to review these two specifications. Implementation-time decisions remain intentionally deferred: Temporal child-workflow versus activity topology, exact Temporal versioning convention, supported long-lived Temporal deployment, SSE versus polling default, provider-specific idempotency capabilities, retention durations, and physical storage vendor semantics.

## Gate

STATE_MACHINES_GATE = READY_FOR_REVIEW
