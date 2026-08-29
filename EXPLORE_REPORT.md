# EXPLORE_REPORT.md — AI 短剧制作 Agent 技术探索报告

> **阶段：EXPLORE（仅调研，不锁定生产架构）**  
> **日期：2026-08-29**  
> **输入基线：** `INTENT.md`（Approved）、`02_DECISIONS.md`（Approved）、`03_PRODUCT_SPEC.md`（Draft）、`04_USER_FLOWS.md`（Draft）、`README(1).md`  
> **约束：** 本报告不修改已批准的 Intent/Decision，不创建生产功能代码，也不代替后续 Architecture、Data Contracts、State Machines、Provider、Evaluation 或 Security 规格。

---

## 0. 执行摘要

现有文档在核心方向上高度一致：面向个人创作者、60–90 秒竖屏短剧、镜头级生产、默认自动推进、异常接管、Mock-first、Provider 可替换、有限修复、成本与 Evidence 全程记录。

已批准的技术栈 **Next.js + FastAPI + PostgreSQL + Temporal + FFmpeg** 仍然适合当前目标，没有发现需要推翻 DEC-010 的证据。

本次 Explore 后，建议进一步明确以下架构原则：

1. **模块化单体优先，不按 Agent 拆微服务。** FastAPI API、Temporal Worker、Media Worker 可以是不同进程，但共享同一 Python 领域代码库和 PostgreSQL 数据模型。
2. **PostgreSQL 保存业务事实，Temporal 保存执行历史。** Temporal 不作为 UI 查询数据库，也不保存完整领域真相。
3. **Shot Graph 与 Timeline 分离。** Timeline 表示播放顺序；Shot Graph 表示执行、派生、连续性、音频同步和失效传播关系。
4. **不宣称 exactly-once。** 采用 `at-least-once execution + business idempotency + provider reconciliation`，将“请求可能已被 Provider 接收但响应丢失”视为一等风险。
5. **Repair Budget 只计算创意/QC 驱动的修复循环。** Transport retry、Provider attempt、candidate generation、deterministic media retry 与 creative repair 必须分离计数。
6. **Mock 必须产生真实可探测媒体文件。** JSON-only mock 不能证明 FFmpeg、字幕、音轨、替换和最终导出链路。
7. **第一 Mock Milestone 不做过早优化。** 不做微服务、LoRA、本地 GPU 集群、对象存储、复杂 Agent 框架、增量区段渲染和完整 SaaS 权限。

### 本报告的 Product Owner 澄清基线

以下问题已经视为本次 Explore 的已解决输入，不再列为开放产品问题：

- 成片生命周期：`ROUGH_CUT_READY → DELIVERABLE_READY → ACCEPTED`；`PUBLISHED` 不属于 MVP 生产完成状态。
- 默认 `target_duration = 60s`，MVP 可接受范围 60–90 秒；片头、片尾和黑场计入最终时长。
- 竖屏 720P 基线：`720×1280`、9:16、30fps、square pixel；精确 codec/profile/audio 参数由 FFmpeg 兼容性实验锁定。
- 单个 Shot 的 `WAITING_HUMAN` 不暂停无依赖镜头；只有预算、安全/权利、不可消解创作歧义、Provider 级不可恢复故障可以形成项目级阻断。
- 只有 QC 驱动的 creative repair 消耗每镜头最多 2 次 Repair Budget。
- 第一个 Mock Milestone 复用未变化资产，但最终 MP4 使用完整、确定性的 FFmpeg 重渲染，不做增量片段缓存。
- Project Copy 不属于第一个 Mock Milestone；版本、回滚、局部替换必须属于第一个 Mock Milestone。

### Gate 结论

**EXPLORE_GATE = PASS**

Explore 阶段已经足够完成：架构方向、关键风险、最小 Mock 范围、未决问题和必要实验已经被识别。  
但这不等于 Architecture 已经批准。进入 `05_ARCHITECTURE.md` 前，应先完成本报告第 10 节标记为 **P0** 的最小技术 Spikes，并保存 Evidence。

---

# 1. Repository assessment（仓库评估）

## 1.1 仓库现状

当前仓库以产品文档为主：

| 文件 | 状态/作用 | 评估 |
|---|---|---|
| `INTENT.md` | Approved — Baseline Locked | 最高层产品合同，完整 |
| `02_DECISIONS.md` | Approved | 关键产品与技术方向已锁定 |
| `03_PRODUCT_SPEC.md` | Draft for Review | 功能覆盖较完整，需要后续把 Explore 结论回写到术语和边界 |
| `04_USER_FLOWS.md` | Draft for Review | 主流程和异常流程完整，需要对项目/镜头局部阻断进一步精确化 |
| `EXPLORE_REPORT.md` | 本报告 | 技术探索与 Gate |
| `README(1).md` | 文档包说明 | 文件名和阶段状态后续可整理，不影响技术探索 |

当前没有生产代码是合理的。现阶段最重要的是验证 durable workflow、幂等、预算、媒体处理和 Shot invalidation 等高风险假设，而不是提前堆页面或模型 SDK。

## 1.2 文档一致性结论

上位文档一致支持：

- 60–90 秒、9:16、720P、30fps、12–24 镜头。
- 最多 2 个主要角色、1–2 个核心场景。
- 默认自动生产到完整草片，异常时才打断用户。
- 镜头级资产、候选、QC、修复和局部重做。
- 持久状态、幂等、恢复、成本控制和 Evidence。
- 每镜头最多 2 次创意/QC 修复。
- Mock-first、Provider 可替换、先工作流后真实付费模型。

因此，当前主要任务不是改变产品方向，而是把“可靠性语义”变成可实现和可测试的工程契约。

---

# 2. Validated decisions（已验证的决策）

## 2.1 保持 DEC-010 技术栈基线

**推荐继续采用：**

- Next.js + TypeScript：Web UI、项目管理、分镜板、异常中心、草片评审。
- FastAPI + Python：领域 API、Provider Adapter、AI/媒体编排接口。
- PostgreSQL：业务事实、版本、预算、成本、Evidence、幂等唯一约束。
- Temporal：跨分钟/小时/天的 durable workflow、timer、retry、signal/update、恢复。
- FFmpeg/ffprobe：确定性媒体探测、转码、合成、字幕和技术 QC。

Next.js 不负责核心生产编排；FastAPI 也不自己实现长任务持久队列。Temporal 处理执行历史，PostgreSQL 处理用户可查询的领域事实。

参考：

- [Next.js Backend for Frontend](https://nextjs.org/docs/app/guides/backend-for-frontend)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Temporal Workflow Definition](https://docs.temporal.io/workflow-definition)
- [Temporal Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies)
- [ffprobe](https://ffmpeg.org/ffprobe.html)

## 2.2 模块化单体，而非微服务/多 Agent 服务化

MVP 不按 Story Agent、Director Agent、QC Agent 拆微服务。

建议部署单元可以拆进程：

```text
web                 Next.js
api                 FastAPI
workflow-worker     Temporal Python Worker
media-worker        FFmpeg / ffprobe task queue
postgres            PostgreSQL
temporal            Temporal dev / managed service
```

但业务代码仍共享：

```text
domain/
application/
workflows/
providers/
media/
repositories/
contracts/
```

逻辑 Agent 只是受 Schema 和状态机约束的能力节点，不需要每个角色拥有独立进程、独立数据库或独立 Agent Framework。

## 2.3 Mock-first 与关键帧先行

Mock 必须生成真实媒体：

- PNG/JPEG 关键帧
- MP4 视频镜头
- WAV/AAC 音频
- SRT 字幕
- 最终 MP4

这些媒体可以通过 FFmpeg/color bars/testsrc/sine wave/静态图片等确定性方式生成，但必须能被 ffprobe 检查。

这样才能真正验证：

- 文件路径和 Storage Adapter
- 帧率和时间基
- 字幕编码
- 音画长度
- Timeline 替换
- 最终重新导出
- crash recovery 后资产复用

---

# 3. Inconsistencies / clarified constraints（不一致与已澄清约束）

## 3.1 已澄清，不再阻断 Architecture

| 编号 | 结论 |
|---|---|
| C-01 | 完成生命周期采用 `ROUGH_CUT_READY → DELIVERABLE_READY → ACCEPTED` |
| C-02 | `PUBLISHED` 不属于 MVP 生产工作流状态 |
| C-03 | 默认目标 60 秒，MVP 允许 60–90 秒，所有片头片尾计入 |
| C-04 | 竖屏媒体基线 720×1280 / 30fps / square pixel |
| C-05 | Transport retry、Provider attempt、Candidate、Media retry、Creative Repair 分开计数 |
| C-06 | 单个 Shot 等待人工不暂停无依赖 Shot |
| C-07 | 只有项目级预算、安全、权利、必要创作决策和 Provider 级硬故障阻断新的项目级付费工作 |
| C-08 | Mock 阶段最终视频完整重渲染，不做增量 GOP/片段缓存 |
| C-09 | 第一个 Mock Milestone 不实现 Project Copy |
| C-10 | 第一个 Mock Milestone 必须实现版本、回滚、局部镜头替换 |

## 3.2 后续规格仍需明确

- Provider、项目、媒体类型的并发和速率限制。
- HTTP、Provider job、Temporal Activity 和项目级 deadline 的不同超时语义。
- BudgetReservation 的释放、过期、退款、失败收费和汇率语义。
- Asset hash、临时文件、原子发布、删除和 scratch directory 清理。
- Workflow / Prompt / Provider request / Evidence Schema 的版本策略。
- Provider webhook 签名、重复回调、乱序、重放攻击和下载校验。
- Evidence 的脱敏和保留期限。
- FFmpeg 版本、字体和渲染容器镜像固定方式。

这些问题不要求在 Explore 阶段全部锁死，但必须在对应的 Architecture / Security / Evaluation Spec 中有明确归属。

---

# 4. Architecture options（架构选项）

## 4.1 总体拓扑

| 选项 | 优点 | 风险 | 结论 |
|---|---|---|---|
| Next.js 全栈 + 简单队列 | 部署少 | AI/媒体 Python 生态差、长任务语义弱 | 不推荐 |
| **Next.js + FastAPI 模块化单体 + Temporal Workers** | 领域边界清晰、durable execution、媒体生态好 | 两运行时、Temporal 学习成本 | **推荐** |
| 按 Agent 拆微服务 | 独立扩容 | MVP 复杂度过高、分布式一致性成本大 | 不推荐 |
| Serverless + 托管工作流 | 运维少 | FFmpeg/长轮询/本地媒体限制、锁定供应商 | 后续再评估 |

## 4.2 两层编排

建议：

### Project Workflow

```text
preflight
→ planning
→ story / screenplay
→ bibles
→ shot planning
→ fan-out shot work
→ timeline
→ rough render
→ deliverable render
```

接收：

- pause
- resume
- cancel
- budget update
- human resolution
- shot selection
- dialogue edit impact approval

### Shot Workflow / Child Workflow

```text
keyframe
→ candidate generation
→ technical QC
→ semantic/continuity QC
→ pass
  or repair cycle 1
  or repair cycle 2
  or waiting-human
```

是否每个 Shot 都必须是独立 Temporal Child Workflow，可以等 P0 Temporal Spike 后再决定；MVP 也可以让 Project Workflow 调度结构化 Shot Activities，只要不会产生无法控制的巨大 history。

## 4.3 Shot Graph

不要把“视频播放顺序”和“生产依赖”混成一张图。

### Timeline

保存：

- 最终播放顺序
- clip in/out
- 字幕与音轨时间
- 转场

### Dependency Graph

建议的 edge type：

- `EXECUTION_REQUIRES`
- `DERIVED_FROM`
- `CONTINUITY_REFERENCE`
- `AUDIO_SYNC`
- `INVALIDATES_ON_CHANGE`

播放先后不等于执行依赖；连续性引用也不一定阻断并行。

修改剧本或台词时：

```text
old version
→ compute impact plan
→ user sees affected assets/cost if paid
→ commit new version
→ invalidate only matching edges
→ reconcile affected work
```

## 4.4 状态分层

避免一个巨型 `ProjectStatus`。

建议分为：

- **Project**：用户理解的聚合状态。
- **Shot**：镜头生产和审核状态。
- **Job / ProviderAttempt**：提交、运行、未知、成功、失败、取消、对账。
- **Asset**：temporary、validated、selected、superseded、delete-pending。
- **Issue / Review**：open、auto-repairing、waiting-human、resolved、accepted-risk。
- **BudgetReservation / CostEvent**：预算和成本生命周期。

状态转换记录至少包含：

```text
from
→ to
reason
actor
correlation_id
causation_id
version
occurred_at
```

## 4.5 幂等、重试和未知提交

正确目标不是“exactly-once”，而是防止重复副作用和重复收费。

### Stable operation_id

每个逻辑副作用产生稳定 `operation_id`：

```text
workspace
+ project
+ entity/version
+ operation_type
+ provider route
+ strategy version
```

PostgreSQL 使用唯一约束防止重复创建同一逻辑操作。

### Provider 提交

- 支持 idempotency key：重复请求使用同一 key。
- 支持 client reference / query：保存外部 job id 并优先 reconcile。
- 请求可能成功但响应丢失：进入 `SUBMISSION_UNKNOWN`。
- `SUBMISSION_UNKNOWN` 未完成对账前，禁止自动重新付费提交。

### Retry taxonomy

| 类型 | 示例 | 是否消耗 2 次 Repair Budget |
|---|---|---|
| Transport retry | timeout / 429 / transient 5xx | 否 |
| Provider attempt | 一次实际提交 | 否，单独计数 |
| Candidate generation | 同镜头候选 1/2/3 | 否，单独计数 |
| Deterministic media retry | FFmpeg worker crash | 否 |
| **Creative repair cycle** | QC 失败后改变 Prompt/route/action | **是** |

## 4.6 Provider Adapter

不设计万能 `generate()`。

核心能力按类型拆：

```text
ImageProvider
VideoProvider
TTSProvider
LipSyncProvider
MusicProvider
ModerationProvider
VisionReviewProvider
```

每个实现暴露 capability descriptor，例如：

- 支持输入模式
- 最大时长/尺寸
- reference 数量
- native audio
- callback / polling
- cancel
- idempotency
- client reference/query
- 区域
- price version
- model version
- content restrictions

业务层决定 Shot route 和 repair policy；Adapter 只负责协议、映射、状态、下载、错误归一化和成本解析。

## 4.7 Storage / Asset

开发期遵守 DEC-011，使用本地文件系统，但从第一天通过 Storage Adapter。

业务数据保存 logical key，而不是 Windows/Linux 绝对路径：

```text
workspaces/{workspace}/projects/{project}/assets/{asset}/{version}/{filename}
```

资产原则：

- 原始和派生文件不可变。
- selected/superseded 是关系状态，不覆盖物理文件。
- 写入临时路径 → 验证 → hash → 原子发布。
- Media Worker 使用每 Job 独立 scratch directory。
- Storage Adapter contract 后续可复用到 S3/OSS。

## 4.8 实时进度

### 推荐：MVP 使用 SSE + 普通 REST 查询兜底

不建议第一版直接上 WebSocket。

理由：

- 当前主要需求是 Server → Browser 的生产事件流。
- 用户不需要通过同一长连接持续双向传控制命令；暂停、恢复、取消可以使用 REST command。
- SSE 更容易穿过普通 HTTP 基础设施，也更容易实现断线重连。
- 页面刷新后仍需通过 REST 从 PostgreSQL 投影重新恢复完整状态，不能依赖 event stream 作为事实源。

建议接口形态：

```text
GET  /projects/{id}
GET  /projects/{id}/events?after=<cursor>   # SSE
POST /projects/{id}/commands/pause
POST /projects/{id}/commands/resume
POST /projects/{id}/commands/cancel
```

事件示例：

```json
{
  "event_id": "...",
  "project_id": "...",
  "subject_type": "shot",
  "subject_id": "SC01_SH07",
  "type": "SHOT_QC_FAILED",
  "stage": "qc",
  "occurred_at": "..."
}
```

### 进度展示原则

不展示虚假的 0–100% ETA。

优先展示：

- 当前 Stage
- shots completed / total
- active jobs
- failed / waiting-human
- spent / reserved budget
- 当前正在做什么

SSE 不是 P0 架构阻断项；如果开发环境 SSE 有兼容问题，Mock Milestone 可先使用 2–3 秒轮询，API 事件模型保持不变。

---

# 5. Temporal risks and alternatives

## 5.1 Temporal 的适用点

本项目存在：

- 长运行任务
- 外部异步 Provider
- timer / polling / callbacks
- pause/resume
- crash recovery
- bounded repair
- fan-out shots
- 需要防止重启后丢状态

因此 Durable Execution 的价值真实存在。

## 5.2 Temporal 的主要风险

### R-TEMP-01 Workflow determinism

Workflow 代码不能随意执行不确定 I/O 或依赖当前时间/随机数；所有副作用必须通过 Activity 或 Temporal API。

**风险：** Codex 若不受约束，很容易把 DB 或 Provider 调用放进 Workflow 逻辑。

**控制：** 在 `AGENTS.md` 和 Architecture 中明确：Workflow 只编排，I/O 全部 Activity 化。

### R-TEMP-02 Workflow version evolution

持续运行的 Project 可能跨部署版本。

**风险：** 直接修改 Workflow 分支会导致 replay nondeterminism。

**控制：** P0 Spike 必须验证 workflow version / patch / continue-as-new 的使用规则，并写进开发规范。

### R-TEMP-03 History growth

12–24 镜头 × 生成 × 轮询 × QC × repair 可能形成很长 history。

**控制：** 避免高频轮询写大量 event；必要时 child workflow / continue-as-new；真实阈值由 Mock benchmark 决定。

### R-TEMP-04 Pause semantics

Temporal 没有“自动冻结所有外部世界”的魔法暂停。

**推荐 cooperative pause：**

1. 持久化 project `pause_intent`。
2. Workflow 收到 signal/update。
3. 新的付费 Activity 调度前检查 pause gate。
4. 已经提交的 Provider job 继续 reconcile。
5. resume 后从 gate 继续。

### R-TEMP-05 Operational cost

自托管 Temporal 本身有数据库、服务和运维成本。

**MVP 建议：** 本地使用官方 dev server / Docker；生产阶段优先评估 managed Temporal，再决定是否自托管。

## 5.3 Temporal vs Celery/Redis

### Celery 优点

- Python 生态成熟。
- 简单异步任务容易。
- 上手成本较低。

### 缺点

本项目仍需自己实现：

- durable orchestration state
- pause/resume semantics
- compensation/reconciliation
- workflow timers
- long-term state
- human wait
- DAG recovery

**结论：** 如果只是“提交视频任务然后轮询”，Celery 足够；但本项目明确要求跨阶段恢复和人工接管，Temporal 更匹配。

## 5.4 Temporal vs PostgreSQL Queue

PostgreSQL queue 可使用 `FOR UPDATE SKIP LOCKED` 等模式完成任务领取。

优点：组件少。

缺点：需要自行实现 retry scheduler、timer、workflow history、pause/resume、fan-out reconciliation、版本迁移和可观测性。

**结论：** 不建议为了省一个组件而自研 durable workflow engine。

## 5.5 Temporal vs Managed Cloud Workflow

AWS Step Functions、GCP Workflows、Azure Durable Functions 等可以承担部分 durable orchestration。

风险：

- 强供应商绑定。
- 本地开发一致性较差。
- 媒体 Worker 与 Provider 编排跨环境调试复杂。

**结论：** MVP 保持 Temporal；生产部署时再比较 Temporal Cloud 与具体云服务。

## 5.6 Temporal Gate

**保留 Temporal，但必须通过 P0 Spike。**

如果 P0 Spike 证明：

- 团队无法稳定处理 replay/versioning，或
- Pause / crash recovery 复杂度明显超过收益，或
- 本地/部署约束不可接受，

则允许在 ADR 中重新评估 Celery/PostgreSQL queue，而不是因为 DEC-010 已批准就强行保留。

---

# 6. Next.js + FastAPI two-runtime risks

## 6.1 主要风险

### API Contract Drift

TypeScript 与 Pydantic schema 可能漂移。

**建议：** FastAPI OpenAPI 作为传输契约来源；自动生成或校验 TypeScript client/types。领域模型不要求 TS 与 Python 源码共享。

### Authentication Boundary

首 Mock 使用固定 local workspace/actor，不实现生产 Auth。

后续生产 Auth 需要：

- Browser 对 Next.js / FastAPI 的认证策略一致。
- FastAPI 不相信浏览器提交的任意 `workspace_id`。
- Provider credential 只在后端。

### Upload / Download Boundary

前端不允许把服务器绝对路径交给用户，也不允许前端持有 Provider key。

Mock：

```text
Browser → FastAPI upload endpoint → Storage Adapter
```

生产：可以升级为受控 direct upload / signed URL，但必须通过授权和 metadata registration。

### Two Runtime Operations

两个运行时意味着：

- 两套依赖管理
- 两个进程生命周期
- API contract
- CORS/proxy

**控制：** 不再增加第三个 Node backend；Next.js 专注 BFF/UI，FastAPI 是唯一领域 API。

## 6.2 推荐 API 边界

Next.js 不直接：

- 调用视频/图片/TTS Provider
- 写 PostgreSQL
- 操作 Temporal
- 执行 FFmpeg

Next.js 只通过 FastAPI：

```text
queries
commands
uploads/download access
progress events
```

这样 Provider 密钥、预算和状态机只有一个可信后端入口。

---

# 7. Mock-first end-to-end architecture

## 7.1 第一 Mock 所需组件

```text
[Next.js Web]
      |
      v
[FastAPI Domain API]
      |
      +---- [PostgreSQL]
      |
      +---- [Temporal Client]
                |
                v
        [Workflow Worker]
          |           |
          v           v
   [Mock Provider] [Media Activities]
          |           |
          +-----+-----+
                v
        [Storage Adapter]
                |
                v
        [FFmpeg / ffprobe]
```

## 7.2 Mock Provider 必须做什么

Mock 不需要生成 AI 画质，但必须模拟真实 Provider 行为：

- sync accepted response
- async job id
- running delay
- success
- transient failure
- permanent failure
- submission accepted but HTTP response lost
- duplicate callback
- out-of-order callback
- rate limit
- cancelable / non-cancelable
- predictable simulated price

媒体结果必须是真实文件。

## 7.3 Mock 媒体策略

关键帧：使用固定色块、shot id、角色/场景标签生成 PNG。  
视频：使用 FFmpeg `testsrc/color/drawtext` 生成 2–5 秒 MP4。  
音频：使用 sine/silence 或固定 WAV。  
字幕：生成真实 SRT。  
Timeline：拼接真实 MP4 和音频。  
技术 QC：ffprobe + 文件检查。

这样 Mock 能证明工程闭环，而不是画质。

## 7.4 明确排除

第一 Mock 不包含：

- Wan 或任何真实付费 Provider
- LoRA
- VLM 视觉质量判定
- 真人声音克隆
- WebSocket
- S3/OSS
- Kubernetes
- 多租户 Auth
- 项目复制
- 增量区段渲染
- 微服务
- LangGraph 等复杂 Agent Framework

## 7.5 Failure Injection Harness

Mock Provider 支持按 shot/job 设置 scenario，例如：

```json
{
  "shot_id": "SC01_SH07",
  "scenario": "submission_unknown"
}
```

至少支持：

```text
worker_crash_after_provider_accept
provider_429_then_success
provider_permanent_failure
provider_submission_unknown
ffmpeg_fail_once
qc_fail_twice
budget_exhausted
pause_during_running_job
duplicate_callback
```

这些 scenario 的测试结果进入 `evidence/`。

---

# 8. Minimum Mock milestone

第一个里程碑只证明一条纵向链路，不追求完整 UI。

## 8.1 必须证明

### M-01 Project creation

可以创建一个《门外的人》Mock Project，保存 Brief 和固定 workspace/actor。

### M-02 Planning persistence

可以保存：

- Story
- Screenplay
- Character/Location/Prop 最小 Bible
- 3–5 个 Mock Shot（技术验证阶段不需要一上来 18 个）

> 真实产品目标仍是 12–24 镜头；Mock 技术纵切先用少量镜头以缩短验证时间。

### M-03 Shot Graph

至少证明：

- 一个 execution dependency
- 一个 continuity reference
- 一个 audio sync
- 一个 invalidation rule

### M-04 Async job

Temporal 启动异步 Mock Provider job，worker 重启后可以恢复。

### M-05 Real media files

生成真实 PNG/MP4/WAV/SRT，并通过 ffprobe。

### M-06 QC + bounded repair

一个 Shot 第一次 QC fail → repair → pass；另一个 Shot 连续两次 creative repair fail → `WAITING_HUMAN`。

### M-07 Independent progress

失败 Shot 进入人工等待时，无依赖 Shot 继续完成。

### M-08 Pause/resume

Pause 后不启动新的模拟付费 operation；in-flight mock job 可以完成 reconcile；Resume 后继续。

### M-09 Crash recovery

在 Provider accept 后杀死 Worker，恢复后不创建重复逻辑 operation。

### M-10 Budget blocking

并发两个 Shot 时 BudgetReservation 原子阻止超限。

### M-11 Shot replacement

替换一个 selected clip 后，Timeline 生成新版本并完整重新 FFmpeg render；未变化素材不重新生成。

### M-12 Dialogue change impact

修改一句台词，impact plan 只标记对应 audio/subtitle/lip-sync/video dependency，不污染无关 Shot。

### M-13 Evidence

形成至少包含以下内容的 EvidenceManifest：

- state transitions
- operations
- job attempts
- media hashes
- ffprobe result
- budget/cost event
- failure injection
- recovery proof
- final render hash

## 8.2 不要求在首 Mock 完成

- 完整精致前端
- 18 个镜头完整样片
- 真实 AI 模型
- 自动 VLM QC
- 商业 Auth
- 云部署
- 对象存储

---

# 9. Unresolved decisions

## 9.1 Must decide before Architecture is approved

1. Temporal P0 Spike 是否证明 crash recovery / replay / pause 可接受。
2. `Project Workflow + Shot Child Workflow` 还是 `Project Workflow + Shot Activities`；由 history/复杂度实验决定。
3. Operation / ProviderAttempt / CostReservation 的幂等和事务边界。
4. Shot Graph edge schema 与 invalidation policy。
5. 数据库与 Temporal 的“单写者/命令入口”规则。
6. 720×1280 最终 Mock codec/audio 参数。

## 9.2 Must decide before real Provider integration

1. 第一批 Image / Video / TTS / Lip-sync Provider。
2. Provider idempotency/reconciliation capability 准入标准。
3. 真实 Provider pricing snapshot 和成本换算。
4. Webhook security。
5. VLM QC 模型与人工基准。
6. 真人声音/肖像授权记录粒度。
7. 对象存储和临时 URL 方案。
8. Provider 区域可用性与数据处理条款。

## 9.3 Can defer beyond first MVP

- Project Copy
- 多用户协作
- SaaS billing
- LoRA 训练
- 本地 GPU cluster
- Kubernetes
- 增量区段 render cache
- WebSocket
- 多语言
- 8–10 分钟长剧

---

# 10. Required technical spikes / experiments

原则：**Spikes 是短实验，不是提前写生产系统。**  
只做能改变架构决策的实验。P0 证据通过后即可进入 Architecture，不要求把所有 P1/P2 实验都做完。

## SPIKE-01 — Temporal durability + pause/resume（P0）

**Question**  
Worker/API 重启后，能否从持久 workflow 状态继续，并正确执行 cooperative pause？

**Hypothesis**  
Temporal 可以在不重复 logical operation 的前提下恢复；pause 可以阻止新的付费 Activity，同时允许 in-flight job reconcile。

**Minimal experiment**

- 一个 Project Workflow。
- 三个模拟 Shot。
- Activity sleep 模拟 Provider。
- 第二个 job accept 后杀 Worker。
- 重启 Worker。
- 中途发 pause，再 resume。

**Pass**

- 已完成 operation 不重复。
- 恢复后继续。
- pause 后不启动新 paid-operation。
- in-flight job 被正确 reconcile。

**Evidence**

- Temporal event history
- DB operation rows
- test logs
- before/after screenshots or CLI output

**Effort** 0.5–1 day。

## SPIKE-02 — Temporal workflow version evolution（P0）

**Question**  
正在运行的 workflow 跨代码版本部署时如何避免 replay nondeterminism？

**Hypothesis**  
通过 Temporal 官方 versioning/patch 方式或兼容分支策略可以安全演进。

**Minimal experiment**

- 启动 v1 workflow 并停在 timer/human wait。
- 部署 v2，改变后续一个分支。
- replay/继续运行。

**Pass**

- 旧 workflow 可以继续。
- 新 workflow 使用新路径。
- replay test 不报 nondeterminism。

**Evidence**

- replay test output
- event history
- versioning note

**Effort** 0.5 day。

> SPIKE-01/02 可以在同一临时 Temporal harness 中完成，不需要两个独立项目。

## SPIKE-03 — Provider unknown submission / idempotency（P0）

**Question**  
Provider 已接受请求但 HTTP response 丢失时，系统是否会重复付费？

**Hypothesis**  
Stable operation_id + Provider client reference + `SUBMISSION_UNKNOWN` + reconcile 能避免盲目重提。

**Minimal experiment**

Mock Provider：

1. 首次 submit 实际创建 job。
2. 客户端收到模拟 timeout。
3. Activity retry。
4. 使用 operation key 查询原 job。

**Pass**

- Provider 只有一个 logical paid job。
- DB 只有一个 operation。
- retry 走 reconcile，不创建第二次 charge。

**Evidence**

- mock provider request log
- operation/provider_attempt rows
- cost events

**Effort** 0.5 day。

## SPIKE-04 — Concurrent budget reservation（P0）

**Question**  
多个 Shot 并发时是否可能同时读取“余额足够”并一起超预算？

**Hypothesis**  
PostgreSQL 事务 + BudgetReservation 可以原子控制。

**Minimal experiment**

- 总预算 100。
- 两个并发 operation 各需 upper-bound 60。
- 并行 reservation。

**Pass**

- 只有一个 reservation 成功。
- 另一个得到明确 budget blocked。
- 无负余额或重复 reservation。

**Evidence**

- concurrency test
- transaction log / rows

**Effort** 0.5 day。

## SPIKE-05 — Shot Graph invalidation（P0）

**Question**  
修改一句台词或更换一个角色 Look 时，系统能否只失效真实依赖资产？

**Hypothesis**  
Typed edges + versioned nodes 能产生稳定 impact plan。

**Minimal experiment**

构建 5-shot graph：

- Shot 2 台词影响 TTS/subtitle/lip-sync。
- Shot 3 continuity reference 不应因普通字幕改动失效。
- Shot 4 使用同一角色 Look。

分别修改台词和 Look。

**Pass**

- impact set 符合预期 fixture。
- graph 保持 DAG。
- 无关 Shot 不失效。

**Evidence**

- graph fixture
- expected vs actual invalidation JSON

**Effort** 0.5–1 day。

## SPIKE-06 — FFmpeg deterministic render（P0）

**Question**  
相同输入和工具版本是否可以稳定输出技术规格正确的最终视频？

**Hypothesis**  
固定 FFmpeg 版本、输入、滤镜和 metadata 后可得到可重复技术结果；字节级 hash 是否完全一致作为实验结果记录，不作为产品硬承诺。

**Minimal experiment**

- 3 个短 MP4
- 1 WAV
- 1 SRT
- 720×1280 / 30fps
- 连续 render 两次
- ffprobe 比较

**Pass**

- 两次技术 metadata 一致。
- 总时长误差在定义范围内。
- 无黑帧/缺音轨/字幕失败。
- Shot replacement 后重 render 正确。

**Evidence**

- FFmpeg command snapshot
- ffprobe JSON
- output artifacts

**Effort** 0.5 day。

## SPIKE-07 — Progress delivery SSE vs polling（P1）

**Question**  
MVP 是否需要 SSE，还是轮询已经足够？

**Hypothesis**  
SSE 适合单向进度事件；轮询可作为兜底；WebSocket 不需要。

**Minimal experiment**

- FastAPI 暴露 event stream。
- Next.js 页面接收 20–50 个模拟事件。
- 断网/刷新重连。

**Pass**

- reconnect 后可以用 cursor 补事件或 REST state 恢复。
- 不需要 WebSocket 才能满足 UX。

**Evidence**

- browser recording/log
- API event fixture

**Effort** 0.25–0.5 day。

**说明：** P1，不阻止开始 Architecture；如果实现成本高，首 Mock 可以轮询。

## SPIKE-08 — FastAPI OpenAPI → TypeScript contract（P1）

**Question**  
如何减少 Next.js 和 FastAPI contract drift？

**Hypothesis**  
OpenAPI 生成 TS types/client 足够，无需共享跨语言领域源码。

**Minimal experiment**

- 3 个核心 endpoint schema。
- 生成 TypeScript types。
- CI 检查 schema drift。

**Pass**

- 改 Pydantic schema 后生成差异可见。
- 前端编译能暴露破坏性变化。

**Evidence**

- generated diff
- CI command output

**Effort** 0.25 day。

---

# 11. Recommended architecture direction

若 P0 Spikes 通过，Architecture 应以以下方向为基线：

```text
                         ┌───────────────────────┐
                         │       Next.js Web     │
                         │ UI / Review / Events  │
                         └───────────┬───────────┘
                                     │ REST + SSE/poll
                                     ▼
                         ┌───────────────────────┐
                         │      FastAPI API      │
                         │ Commands / Queries    │
                         └──────┬────────┬───────┘
                                │        │
                                │        └───────────────┐
                                ▼                        ▼
                       ┌────────────────┐       ┌────────────────┐
                       │   PostgreSQL   │       │ Temporal Client│
                       │ domain truth   │       └───────┬────────┘
                       └────────────────┘               ▼
                                               ┌───────────────────┐
                                               │ Project Workflow  │
                                               │ Shot orchestration│
                                               └───────┬───────────┘
                                                       │ Activities
                                  ┌────────────────────┼─────────────────┐
                                  ▼                    ▼                 ▼
                         ┌────────────────┐   ┌────────────────┐  ┌───────────────┐
                         │ Mock/Provider  │   │ Media Worker   │  │ QC Activities │
                         │   Adapters     │   │ FFmpeg/ffprobe │  │ rules / later │
                         └───────┬────────┘   └───────┬────────┘  └───────────────┘
                                 │                    │
                                 └─────────┬──────────┘
                                           ▼
                                  ┌──────────────────┐
                                  │ Storage Adapter  │
                                  │ local → S3/OSS   │
                                  └──────────────────┘
```

### Domain truth

PostgreSQL 保存：

- Project / Brief / Story / Script versions
- Character / Look / Location / Prop
- Shot / ShotVersion / DependencyEdge
- Asset / AssetLineage / Selection
- Operation / ProviderAttempt / InboxEvent
- Review / Issue / RepairCycle
- Timeline / TimelineVersion
- Budget / BudgetReservation / CostEvent
- EvidenceRecord / StateTransition

### Workflow truth

Temporal 保存：

- 当前执行到哪一步
- timer / retry
- fan-out / join
- signal / update
- Activity result history

不要把 Temporal history 复制成领域数据库，也不要让 UI 直接依赖 Temporal query 作为唯一数据源。

### AI boundary

LLM/VLM 未来负责：

- story planning
- screenplay
- shot planning
- route recommendation
- continuity analysis
- QC diagnosis
- repair planning

确定性系统负责：

- state transition
- operation id
- budget
- provider submission
- retry policy
- asset publish
- FFmpeg
- technical QC
- authorization
- Evidence

---

# 12. EXPLORE Gate checklist

| Gate | 状态 | 说明 |
|---|---|---|
| Intent 未被修改 | PASS | 保持批准版本 |
| Decisions 未被静默改写 | PASS | DEC-010 等保持 |
| 技术栈方向有理由 | PASS | 暂无推翻证据 |
| 微服务风险识别 | PASS | 模块化单体优先 |
| Temporal 风险识别 | PASS | 已列出 P0 验证 |
| Next.js/FastAPI 边界识别 | PASS | FastAPI 为唯一领域 API |
| Shot Graph 语义识别 | PASS | Timeline 与依赖图分离 |
| 幂等与重复付费风险识别 | PASS | SUBMISSION_UNKNOWN / reconciliation |
| Repair 计数边界识别 | PASS | 仅 creative repair 计入 2 次 |
| Mock 最小架构定义 | PASS | 真实媒体 + failure injection |
| 成本并发风险识别 | PASS | BudgetReservation |
| Evidence 方向定义 | PASS | 可导出派生索引 |
| 必要 Spikes 定义 | PASS | 6 个 P0 + 2 个 P1 |
| 真实 Provider 已锁定 | NOT REQUIRED | 应在真实 Provider 阶段再决定 |
| Production Architecture 已批准 | NOT YET | 需 P0 Evidence |

## Gate judgement

**EXPLORE_GATE = PASS**

含义：

- 不需要继续扩大 Explore 文档。
- 不需要再做一轮大范围技术研究。
- 可以开始 P0 Spikes。
- P0 Spikes 只验证关键架构风险，不开发产品功能。
- P0 Evidence 通过后，直接编写 `05_ARCHITECTURE.md`、`06_DATA_CONTRACTS.md`、`07_STATE_MACHINES.md`。

---

# 13. Recommended next step（推荐下一步）

## 13.1 Product Owner 现在需要批准的事情

批准本报告的 Explore Gate 结论，以及 P0 Spikes 的范围。

不需要逐条批准每一个技术细节；具体实现结论由 Evidence 决定。

## 13.2 Codex 下一任务

执行一个**临时 `spikes/` 技术验证 Harness**，仅实现：

1. SPIKE-01/02 Temporal durability + versioning + pause/resume
2. SPIKE-03 Provider unknown submission / idempotency
3. SPIKE-04 concurrent budget reservation
4. SPIKE-05 Shot Graph invalidation
5. SPIKE-06 FFmpeg deterministic render

P1 的 SSE 和 OpenAPI/TS contract 可以在 P0 之后做，不阻断 Architecture。

## 13.3 Evidence 输出

建议只生成一份轻量报告：

```text
SPIKE_EVIDENCE.md
```

并保存必要 artifact 到：

```text
evidence/spikes/
```

不要为每个 Spike 创建大量 ADR 和独立文档。

每项只记录：

- hypothesis
- command/test
- result
- evidence path
- PASS / FAIL
- architecture consequence

## 13.4 Architecture Gate

只有以下情况需要回到 Product Owner：

- P0 Spike FAIL，需要改变已批准的 DEC-010 或关键产品能力。
- 需要增加新的重大基础设施。
- 预算/安全/用户体验边界发生变化。

如果 P0 全部 PASS，则直接进入：

```text
05_ARCHITECTURE.md
06_DATA_CONTRACTS.md
07_STATE_MACHINES.md
08_PROVIDER_SPEC.md
09_EVALUATION_SPEC.md
10_SECURITY_AND_RIGHTS.md
```

随后才编写 `IMPLEMENTATION_PLAN.md`。

---

## 调研证据与局限

本报告基于现有项目文档和官方技术文档方向形成。真实 Provider 的最新价格、区域可用性、模型质量、中文口型和 VLM QC 能力仍需要在 Provider Integration 阶段用基准样片验证，不能由本 Explore 报告直接锁定。

---

> **STOP / WAITING FOR PRODUCT OWNER APPROVAL**  
> `EXPLORE_GATE = PASS`。本阶段不创建生产功能代码；下一步仅执行已定义的 P0 技术 Spikes，并用 Evidence 决定 Architecture。