# 10_SECURITY_AND_RIGHTS.md — Beta Security, Privacy, and Rights

## 1. Security boundary

The Beta is a private, Chinese-mainland-first service for 10–20 invited users. It has no public publishing automation, anonymous access, team billing, or use of unlicensed scraped reference media.

Security controls are enforced by FastAPI and deterministic workers. LLM/VLM output cannot grant access, waive rights, approve content, raise a budget, or release a blocked asset.

## 2. Identity and authorization

- Use an OpenID Connect identity provider with MFA available for Product Owner and operators. The specific managed provider requires Product Owner commercial approval before Week 14.
- JWTs are accepted only from configured issuers and validated for signature, issuer, audience, expiry, not-before, and nonce/state where applicable.
- Every request resolves one `Actor` and `Workspace`; object queries always include `workspace_id`.
- Initial roles are `OWNER`, `CREATOR`, and `REVIEWER`. Only `OWNER` can change budgets, invite users, delete a project, or accept a deliverable.
- Service credentials use workload identity or short-lived credentials where supported. Personal user tokens cannot operate workers.
- Authentication failures and denied authorization decisions are auditable without logging tokens.

## 3. Rights and consent

An immutable `RightsAttestation` is required before any paid operation using an uploaded portrait, voice, motion reference, script, music, or protected footage. It records actor, workspace, asset hash, asserted rights, allowed purposes, territory, expiry if supplied, policy version, and timestamp.

Missing, expired, or revoked rights open a project execution gate. The system does not scrape people, remove third-party watermarks, imitate a public figure, or publish without final user confirmation.

Voice cloning and portrait animation are disabled by default. Product Owner must explicitly enable the capability and approve its consent language before any benchmark.

## 4. Content safety

- Inputs are checked before provider submission; outputs are checked before immutable publication and again before final acceptance.
- Provider safety results are preserved as facts but do not replace application policy.
- Blocking categories include illegal content, non-consensual sexual content, minors in sexual contexts, credible impersonation/fraud, prohibited violence, and missing rights for identifiable people.
- Uncertain cases create a human review Issue. Blocked media is never served through a browser URL.
- Policy and provider model versions are stored with every decision.

## 5. Upload, media, and network safety

- Uploads use a temporary object key and bind expected size, MIME type, extension, workspace, hash, and expiry.
- Initial limits: images 10 MB, audio 50 MB, video 500 MB, text/JSON 2 MB. Archives and executable formats are rejected.
- Validate magic bytes, decode/probe media, reject path traversal, cap pixel count/duration, and run malware scanning before publication.
- Media tools run with no provider credentials, restricted filesystem access, time/memory/process limits, and no unrestricted outbound network.
- Server-side URL fetching is denied by default. Approved provider downloads require HTTPS, an allowlisted host, DNS/IP revalidation, redirect limits, byte limits, and blocks for loopback, link-local and private networks.

## 6. Storage and retention

Production storage is a private Alibaba Cloud OSS bucket in the same mainland region as the application. Access uses V4 presigned URLs: uploads expire after 60 seconds and downloads after 10 minutes. URLs are bearer tokens and are never written to durable logs or Workflow history.

- Temporary uploads and failed validation objects: delete within 24 hours.
- Provider staging downloads: delete within 24 hours after immutable publication.
- User-deleted projects: revoke access immediately and delete media within 30 days, subject to an active legal/security hold.
- Operational logs: 30 days; security audit events and release Evidence: 180 days for Beta.
- Backups follow the same workspace isolation and deletion schedule; restoration access is limited to operators.

Objects use server-side encryption, private bucket policy, least-privilege RAM roles, versioning for immutable production assets, and lifecycle rules. Browser responses never expose local paths or permanent provider URLs.

## 7. Provider callback and secret handling

- Provider callback endpoints require the provider signature or a per-provider HMAC secret, timestamp, and replay window no longer than five minutes.
- The raw body hash and provider event ID form a unique `CallbackInbox` key. Duplicate events return success without duplicate transitions.
- Unknown external job IDs are quarantined for investigation and cannot attach to a project by guesswork.
- Secrets live only in the deployment secret store, are separated by environment, rotated before Beta, and redacted from exceptions, logs, Evidence, prompts, and Workflow payloads.

## 8. Data and infrastructure decision

- Primary region: Alibaba Cloud China North 2 (Beijing), subject to account and Product Owner approval.
- Domain database: dedicated RDS PostgreSQL instance/database with encrypted connections and automated backups.
- Temporal persistence: a separate PostgreSQL database and credentials; never share the application schema or role.
- Temporal service: pinned official server release on private ECS/systemd or private containers, reachable only from trusted subnets through TLS. Port 7233 is not public.
- Object storage: private OSS in the same region. Cross-region replication is disabled until data-transfer review.
- Development, test, staging, and Beta use separate credentials, databases, buckets, namespaces, callback secrets, and encryption keys.

## 9. Verification and incident rules

Required tests cover workspace horizontal/vertical authorization, token validation, signed callback replay, upload type/size spoofing, path traversal, SSRF/DNS rebinding, duplicate events, secret redaction, rights-gate enforcement, object URL expiry, deletion, backup restore, and access revocation.

Duplicate paid submission, cross-workspace disclosure, unrecoverable asset loss, leaked credential, or bypassed rights/safety gate is a P0 incident and immediately stops Beta expansion.

`WEEK_02_SECURITY_SPEC = READY_FOR_PRODUCT_OWNER_REVIEW`

## 10. Official references

- Temporal self-hosted deployment: https://docs.temporal.io/self-hosted-guide/deployment
- Temporal self-hosted operations and security guide: https://docs.temporal.io/self-hosted-guide
- Alibaba Cloud OSS V4 presigned download: https://help.aliyun.com/en/oss/developer-reference/python-download-using-a-presigned-url
- Alibaba Cloud OSS presigned upload: https://help.aliyun.com/en/oss/developer-reference/upload-an-object-using-a-signed-url-generated-with-oss-sdk-for-python
- Alibaba Cloud RDS PostgreSQL backup options: https://www.alibabacloud.com/help/en/rds/apsaradb-rds-for-postgresql/backup-2/
