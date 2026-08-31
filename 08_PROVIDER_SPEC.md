# 08_PROVIDER_SPEC.md — Real Provider Integration

## 1. Status and scope

Status: proposed for Product Owner approval.

This specification defines the first real-provider benchmark and the stable adapter boundary. It does not authorize paid calls, accept provider terms, or place secrets in the repository.

The first deployment is China-first. Provider inference, application data, PostgreSQL, and object storage remain in a Chinese mainland region unless Product Owner and security review approve a documented exception.

## 2. Capability boundary

Every external capability implements the same lifecycle operations:

```python
class ProviderAdapter(Protocol):
    def submit(self, request: ProviderRequest) -> ProviderSubmission: ...
    def status(self, provider_job_id: str) -> ProviderObservation: ...
    def cancel(self, provider_job_id: str) -> ProviderObservation: ...
    def reconcile(self, operation_id: str, client_reference: str) -> ReconciliationProof: ...
```

`ProviderRequest` contains a stable `operation_id`, provider-independent capability, immutable input asset references, model route/version, parameters, callback URL, content-safety identifier, and approved maximum cost. Provider responses are normalized and raw bodies are retained only in access-controlled Evidence after secret and personal-data redaction.

Required capabilities are `IMAGE`, `VIDEO`, `TTS`, `LIP_SYNC`, and `VLM_QC`. Music for the first real MVP uses an approved licensed library or deterministic generated bed; it is not allowed to silently ingest unlicensed media.

## 3. Submission and reconciliation

- One logical paid action has one stable `operation_id` and one active `BudgetReservation`.
- `client_reference` is derived from the operation ID and sent whenever the provider supports a client identifier.
- A transport failure after request transmission moves the Operation to `SUBMISSION_UNKNOWN`.
- `SUBMISSION_UNKNOWN` can only enter `RECONCILING`; it never retries `submit` directly.
- Resubmission is allowed only when the provider or a signed callback proves no matching paid job exists. The same Operation is reused and a new ProviderAttempt is recorded.
- Provider output is downloaded to temporary storage, probed, hashed, safety-checked, and atomically published before the Operation succeeds.
- Callback and polling observations pass through the same inbox de-duplication and state-transition policy.

Normalized error classes are `RATE_LIMITED`, `TRANSIENT_PROVIDER`, `SUBMISSION_UNKNOWN`, `CONTENT_REJECTED`, `INVALID_INPUT`, `QUOTA_EXHAUSTED`, `AUTHENTICATION_FAILED`, `TERMINAL_PROVIDER`, and `OUTPUT_VALIDATION_FAILED`.

## 4. Candidate routes

| Capability | Primary benchmark | Secondary benchmark | Required evidence |
| --- | --- | --- | --- |
| Image/keyframe | Alibaba Cloud Model Studio Wan image generation, Beijing | Volcengine Ark image generation, Beijing | Chinese prompt handling, 9:16 output, identity/prop continuity, async semantics |
| Video | Alibaba Cloud Model Studio Wan video generation, Beijing | Volcengine Ark Seedance video generation, Beijing | image-to-video quality, duration/profile, task query/cancel/callback, safety results |
| TTS | Model Studio CosyVoice, Beijing | an approved Volcengine speech model | Mandarin naturalness, timing control, pronunciation, license and voice-right rules |
| Lip sync | Model Studio digital-human/lip-sync route | Volcengine video lip-sync route | Mandarin sync, face stability, input/output rights terms, failure behavior |
| VLM QC | Model Studio Qwen visual/video understanding | Volcengine Ark vision model | schema-constrained JSON, issue-code precision/recall, no direct domain mutation |

The same vendor may be selected for several capabilities to reduce credential and reconciliation complexity, but product policy must not import vendor SDK types. Model IDs are configuration, pinned per route, and changed only through a versioned route update.

## 5. RMB 500 benchmark budget

| Capability | Maximum spend | Minimum sample |
| --- | ---: | --- |
| Image | RMB 40 | 10 prompts across two routes |
| Video | RMB 300 | 8 representative shots across available routes |
| TTS | RMB 30 | 10 dialogue lines with timing evidence |
| Lip sync | RMB 100 | 4 short dialogue clips across available routes |
| VLM QC | RMB 30 | 10 labeled clips or equivalent frames |

The benchmark stops before a call that would exceed either its capability cap or the total RMB 500 cap. Free quota still creates an `is_paid=false` CostEvent with the observed list price and free-quota basis.

Routes are scored with fixed weights: quality 40%, reliability/reconciliation 20%, cost 15%, latency 10%, Chinese-mainland/data terms 10%, and exit portability 5%. A route must also pass all mandatory safety, rights, stable-operation, result-retention, and output-download checks; score cannot override a mandatory failure.

## 6. Operational policy

- Secrets are injected by the deployment secret store and never returned to the browser, Workflow history, logs, or Evidence.
- Each provider has separate dev/staging/beta credentials, quotas, and callback signing secrets.
- Concurrency is capped per documented provider limits and adjusted by observed throttling.
- Polling uses bounded exponential backoff with jitter. Provider-recommended minimum intervals take precedence.
- Provider result URLs are treated as temporary; accepted outputs are copied immediately to controlled storage.
- A route can be disabled with a feature flag. Failover never occurs until the original operation is reconciled.

## 7. Gate

Before real calls, Product Owner must approve: provider accounts and terms, benchmark budget, Chinese-mainland data handling, voice/portrait policy, and model routes to test.

`WEEK_02_PROVIDER_SPEC = READY_FOR_PRODUCT_OWNER_REVIEW`

## 8. Official references

- Alibaba Cloud Model Studio video generation: https://help.aliyun.com/en/model-studio/use-video-generation
- Alibaba Cloud Wan image API: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference
- Alibaba Cloud CosyVoice and TTS models: https://help.aliyun.com/en/model-studio/tts-model/
- Alibaba Cloud visual understanding: https://help.aliyun.com/zh/model-studio/vision-model/
- Alibaba Cloud model pricing: https://help.aliyun.com/zh/model-studio/model-pricing
- Volcengine Ark API documentation: https://api.volcengine.com/api-docs/?serviceCode=ark&version=2024-01-01
- Volcengine video-generation task API: https://api.volcengine.com/api-explorer/?action=CreateContentsGenerationsTasks&groupName=%E8%A7%86%E9%A2%91%E7%94%9F%E6%88%90API&serviceCode=ark&version=2024-01-01

