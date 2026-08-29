# EXPLORE_REPORT.md — AI 短剧制作 Agent 技术探索报告

> **阶段：EXPLORE（仅调研，不锁定生产架构）**  
> **日期：2026-08-29**  
> **输入基线：** `INTENT.md`（Approved）、`02_DECISIONS.md`（Approved）、`03_PRODUCT_SPEC.md`（Draft）、`04_USER_FLOWS.md`（Draft）、`README(1).md`  
> **约束：** 本报告不修改已批准的 Intent/Decision，不创建应用代码，也不代替后续 Architecture、Data Contracts、State Machines、Provider、Evaluation 或 Security 规格。

---

## 0. 执行摘要

现有文档在核心方向上高度一致：面向个人创作者、60–90 秒竖屏短剧、镜头级生产、默认自动推进、异常接管、Mock-first、Provider 可替换、有限修复、成本与 Evidence 全程记录。已批准的技术栈 **Next.js + FastAPI + PostgreSQL + Temporal + FFmpeg** 能满足目标，未发现必须推翻 DEC-010 的证据。

但不应立即锁定完整生产架构。最大的未知并非 CRUD 或页面技术，而是：

1. 外部 Provider 通常无法提供真正的端到端 exactly-once；“提交成功但响应丢失”会形成重复付费风险。
2. Temporal 的确定性、版本演进、取消/暂停语义及自托管运维成本，需要用故障注入证明团队能够正确使用。
3. Shot Graph 同时混合播放顺序、连续性、生成与资产依赖，若不拆分边类型，局部失效会过度重做或漏做。
4. “每镜头最多 2 次修复”的计数边界、项目/镜头状态职责、预算预留与最终成本结算尚不精确。
5. VLM QC、角色一致性、中文口型、真实 Provider 价格/可用性必须经基准样片实测，不能靠架构推断。

**建议方向：** 采用模块化单体而非微服务；PostgreSQL 保存业务事实，Temporal 保存执行历史，Storage Adapter 保存不可变媒体，FFmpeg/ffprobe 做确定性媒体处理；以显式的 Job/ProviderAttempt/Asset/CostEvent/Evidence 记录连接各层。第一 Mock 里程碑只实现一条纵向闭环与故障注入 Harness，不提前建设真实 Provider、复杂 Agent 框架、WebSocket 基础设施、对象存储或完整 SaaS 权限。

**Gate 建议：** 先完成本文第 10 节的 spikes，尤其是 Temporal 恢复/版本、Provider 不确定提交、FFmpeg 可复现性和进度通道实验；证据通过后，才编写生产架构与数据契约。

---

# 1. Repository assessment（仓库评估）

## 1.1 仓库现状

仓库当前只包含五份产品文档与 Git 元数据，没有应用代码、依赖清单、测试、CI、架构/数据契约/状态机文档或媒体样例。因此，本次“整个仓库检查”的对象就是：

| 文件 | 状态/作用 | 评估 |
|---|---|---|
| `INTENT.md` | Approved — Baseline Locked | 最高层目标、硬约束、成功指标、Mock-first 与停止条件完整；未修改 |
| `02_DECISIONS.md` | Approved | 17 个已批准决策与 Explore 清单清楚；未修改 |
| `03_PRODUCT_SPEC.md` | Draft for Review | 功能覆盖完整，但若干术语和状态边界需在后续规格澄清 |
| `04_USER_FLOWS.md` | Draft for Review | 主流程、异常、编辑和导出路径清晰；部分流程语义与高层状态未完全闭合 |
| `README(1).md` | 文档包说明 | 仍写着 Explore “Not Started”，且原建议是在 Product Spec/User Flows 锁定后 Explore；本次 Product Owner 的明确指令已启动 Explore |

没有发现隐藏的实现、历史架构或可复用脚手架。仓库极简使方向清晰，但也意味着所有技术结论目前都是待验证假设。

## 1.2 文档一致性结论

以下主线在所有上位文档中一致：

- MVP 范围：60–90 秒、9:16、720P、30fps、12–24 镜头、最多 2 个主要角色、1–2 个核心场景、中文普通话。
- 自动化：启动确认后自动运行到完整草片；只有阻断异常与最终发布需要人介入。
- 生产单元：镜头级资产、候选、QC、修复与局部重做，而非整片黑盒。
- 可靠性：持久化状态、显式状态转换、幂等、恢复、已完成资产复用。
- 治理：修复最多 2 次、付费前预算阻断、安全与权利确认、不可静默降级。
- 研发：Mock-first、Evidence-gated、先稳定工作流再接真实付费模型。
- 技术基线：Next.js、FastAPI、PostgreSQL、Temporal、FFmpeg；Storage/Provider 通过 Adapter 隔离。

因此，产品方向可以继续 Explore；下面的问题是“需要精确定义或实验”，不是对已批准要求的变更。

---

# 2. Validated decisions（已验证的决策）

## 2.1 保持 DEC-010 技术栈基线

**推荐：** 保持 Next.js + TypeScript、FastAPI + Python、PostgreSQL、Temporal、FFmpeg，不在 Explore 阶段替换。

**为什么：**

- Next.js 适合项目列表、分镜板、时间线预览和异常中心；其官方文档也明确把 Route Handlers 定位为 Backend-for-Frontend，并提示它不是完整后端替代品，这支持由 FastAPI 承担领域 API，而不是把生产编排塞进前端运行时。[Next.js Backend for Frontend 指南](https://nextjs.org/docs/app/guides/backend-for-frontend)
- Python 是 AI SDK、媒体分析和数据处理的共同语言；FastAPI 提供 OpenAPI、类型验证和异步 HTTP 边界，适合 Provider 与工作流控制面。[FastAPI 文档](https://fastapi.tiangolo.com/)
- PostgreSQL 适合关系完整性、版本/事件元数据、预算账本、幂等唯一约束和查询视图；`LISTEN/NOTIFY` 可作为轻量失效通知，但官方说明通知在事务提交后交付，因此它不应承担持久任务队列。[PostgreSQL NOTIFY](https://www.postgresql.org/docs/current/sql-notify.html)
- Temporal 的 durable execution、Activity retry、timer、signal/update 适配跨小时/天的生产流程；工作流重放要求确定性，这正好迫使编排逻辑与不确定的 Provider I/O 分离。[Temporal Workflow Definition](https://docs.temporal.io/workflow-definition)
- FFmpeg/ffprobe 是编码、拼接、音轨、字幕和技术探测的成熟确定性工具；ffprobe 支持机器可读输出，适合作为技术 QC 证据。[ffprobe 文档](https://ffmpeg.org/ffprobe.html)

**替代方案：** Next.js 全栈、Python 单体服务端渲染、Node 后端、Redis/Celery、云厂商队列、Prefect/Dagster、纯 PostgreSQL 队列、托管媒体服务。

**权衡：** 已选栈增加两个应用运行时与 Temporal 运维，但避免让 Node 承担 AI/媒体生态适配，也比自行实现 durable workflow 更可靠。现阶段替换的迁移收益没有证据。

## 2.2 验证“模块化单体优先”，而非微服务/多 Agent

**推荐：** FastAPI API、Temporal worker 和 media worker 可以是独立进程/容器，但共享一个 Python 领域代码库和 PostgreSQL schema；按部署进程隔离资源，不按“故事 Agent/导演 Agent/QC Agent”拆微服务。

**为什么：** MVP 只有单创作者和一条基准流程。状态、预算、资产与失效传播需要强一致边界；过早拆服务会引入分布式事务、契约发布和可观测性成本。LLM 节点只是受 Schema 约束的 Activity，不需要每个逻辑角色拥有独立框架。

**替代方案与权衡：**

- 单进程：最简单，但 FFmpeg 或高并发轮询会影响 API。
- 微服务：独立扩缩容强，但两周 Mock 里程碑不值得其运维/契约成本。
- 模块化单体 + 多 worker queue：提供足够隔离，也保留以后按热点拆分的路径；这是当前最佳平衡。

## 2.3 验证 Mock-first 与关键帧先行

**推荐：** Mock 必须生成真实可探测的图片、视频、音频和字幕文件，而不是只在数据库把任务标成成功；关键帧是高成本视频前的显式 Gate。

**为什么：** 只有真实容器格式才能暴露时间基、帧率、音频采样率、路径、FFmpeg 转义和替换重导出问题。关键帧能以低成本先验证身份、场景、道具与构图，符合成本约束。

**替代方案：** JSON-only mock 很快但无法证明媒体闭环；直接真实 Provider 可验证画质但会掩盖幂等与恢复缺陷并消耗预算。

**证据：** 上位文档明确要求 Mock 资产经过真实任务队列、状态机和 FFmpeg 成片；ffprobe 可输出稳定的机器可读媒体元数据作为 Gate 证据。[ffprobe 文档](https://ffmpeg.org/ffprobe.html)

---

# 3. Inconsistencies found（不一致、歧义与缺失约束）

## 3.1 需要 Product Owner 澄清但不阻断 Explore

| 编号 | 发现 | 影响 | 建议澄清（不在本报告改需求） |
|---|---|---|---|
| I-01 | `README(1).md` 说 Product Spec/User Flows 锁定后才 Explore，但二者仍是 Draft | Gate 状态与本次阶段不一致 | 将本次明确指令视为 Explore 授权；后续由 PO 决定是否先批准两份 Draft |
| I-02 | `COMPLETED` 有两种时点：技术 QC 后产出生产包，或“用户确认下载/发布”后 | 状态机、通知与验收会不同 | 区分 `DELIVERABLE_READY`、用户 `ACCEPTED` 与外部 `PUBLISHED`；是否新增状态由后续状态机评审决定 |
| I-03 | 默认目标时长在用户流程为 60 秒，但 MVP 承诺是 60–90 秒 | 60 秒是否包含端点、黑场不清 | 明确 target duration、允许窗口及片头片尾是否计入 |
| I-04 | “720P”未明确竖屏像素、SAR/DAR、编码 profile、色彩空间、音频 codec/sample rate | FFmpeg Gate 无法唯一判定 | 后续 Evaluation/Delivery Spec 固定如 720×1280、方形像素及容器编码参数；需设备兼容测试后锁定 |
| I-05 | 技术 QC、视觉 QC 失败都使用“每镜头 2 次修复”，但重新封装、Provider 可恢复重试、候选生成与创意修复的计数边界不清 | 可绕过上限或过早人工接管 | 分离 transport attempt、candidate attempt、repair cycle、deterministic transcode attempt；只有受控 repair cycle 使用两次预算 |
| I-06 | `WAITING_USER` 是 Project 状态，但单镜头失败不应阻塞无依赖镜头 | 全局状态可能停止过多工作 | Project 派生健康状态与 Shot/Issue 局部阻断分离；仅预算/安全/必要创作决策触发全局付费启动 Gate |
| I-07 | Project 与 Shot 状态枚举未覆盖规划、音频、字幕、渲染、取消中、对账未知等细节 | 强塞状态会产生非法跳转 | 高层状态留作用户视图；Job/Asset/Review/Issue 各自拥有生命周期，后续状态机明确聚合规则 |
| I-08 | “暂停”要求不启动新付费任务，但已提交任务继续对账；没有定义暂停一致点、Temporal workflow 自身是否暂停 | 恢复后可能漏事件或重复调度 | 定义 cooperative pause：写入持久 pause intent，workflow 在每次调度付费 Activity 前检查；in-flight job 继续 reconcile |
| I-09 | “任务重放不得重复付费”容易被理解成 exactly-once，但第三方 Provider 未必接受幂等键或按客户 request ID 查询 | 最高财务风险 | 把能力表中的 idempotency/reconciliation 作为 Provider 准入条件；无法对账时进入 `UNKNOWN` 人工处理，不自动重提 |
| I-10 | Shot Graph 同时表达播放顺序、首尾帧、道具、台词、并行与修改影响 | 边的语义与失效传播不明确，DAG 也可能出现创作循环 | 使用带类型、有方向、版本化的依赖边；播放顺序放 Timeline，生产依赖保持 DAG；连续性引用不等同于执行阻塞 |
| I-11 | 修改台词前要求展示影响并确认，与“默认只有三类必要干预”表面冲突 | 主动编辑是否属于额外 Gate | 这是用户主动操作后的成本确认，而非自动主流程 Gate；应在 UX 文案中明确 |
| I-12 | `SRT 或等价格式` 与“字幕样式预览”混在一起；SRT 不完整承载样式 | 导出与预览不一致 | 文本/时间语义与渲染样式分开；SRT 用于交换，样式另存结构化模板或 ASS（待兼容性测试） |
| I-13 | “只重合成受影响区段或最终文件”没有定义是否必须增量渲染 | 可能过早优化且引入 GOP/音频接缝问题 | Mock 先复用源资产但完整重渲染最终文件；是否区段缓存由 benchmark 决定 |
| I-14 | 项目复制、版本回滚、删除都在 Product Spec，User Flows 又把“项目复制是否进入 MVP”列为待评审 | 两周 Mock 范围不确定 | Mock 必须证明版本回滚（上位 Intent）；项目复制是否在首 Mock 里程碑由 PO 决定 |
| I-15 | Evidence 要保留输入/Prompt/日志，删除与隐私要求又要求资产可删除；没有保留期限与脱敏规则 | 审计和删除权冲突 | Evidence 保存哈希、ID、结构化摘要与必要元数据；凭证、签名 URL、敏感原文不得进入清单；保留策略交安全规格 |
| I-16 | 技术通过率 ≥95% 对 12–24 镜头项目可能意味着允许一个失败镜头，但 `COMPLETED` 又不得包含未通过技术校验的成片 | 指标分母和 Release Gate 不清 | 区分 generation-attempt 技术通过率与 selected deliverable 的 100% 技术合格要求 |
| I-17 | 成本要求按项目/场景/镜头查看，但项目级故事、音乐、最终渲染不天然属于某镜头 | 归因会失真 | CostEvent 支持可空 scene/shot 与 allocation rule；展示“直接成本”和“分摊成本” |
| I-18 | 第一版单用户但又要求用户资产访问控制，首版登录未决 | 无主体就无法定义授权/删除审计 | Mock 使用固定本地 workspace/actor，仍在每条记录保留 `workspace_id`/`actor_id`；不等于生产 Auth 方案 |

## 3.2 缺失的技术约束

后续规格至少还需明确：

- **并发与配额：** 每项目/Provider/媒体类型并发上限、速率限制、背压与公平调度。
- **超时层级：** HTTP timeout、Provider job timeout、Activity start-to-close/schedule-to-close、项目 deadline 各自含义。
- **预算语义：** 货币精度、税费/汇率、预估价版本、预留（reservation）、最终结算、退款/失败收费和并发竞态。
- **资产完整性：** 内容哈希、原始/派生关系、原子写入、临时文件清理、恶意文件扫描、大小/时长上限。
- **Schema 演进：** 文档、Prompt、Provider input/output、workflow 与 Evidence 的版本兼容策略。
- **删除与备份：** 软删除/硬删除、Temporal history、数据库备份和对象存储版本中的清除边界。
- **进度定义：** 阶段/计数/事件，不提供虚假线性百分比或 ETA；重试时如何显示回退。
- **人工接管租约：** 谁持有 issue、何时超时、恢复后如何解除暂停，避免自动与人工同时修改。
- **Provider 回调安全：** 签名、重放窗口、重复/乱序回调、出站 URL 防 SSRF、下载内容校验。
- **媒体 reproducibility：** FFmpeg 版本、字体、filter 参数、seed、时区/locale 和容器镜像摘要。
- **Shot Graph 失效规则：** 每种 edge 的 invalidation policy、版本快照、影响预览及用户确认后的原子提交。

---

# 4. Architecture options（架构选项）

## 4.1 总体拓扑选项

| 选项 | 优点 | 风险/代价 | 结论 |
|---|---|---|---|
| A. Next.js 全栈 + 队列 | 单语言、部署少 | AI/媒体 Python 生态割裂；长任务与密钥边界弱；与 DEC-010 不符 | 不推荐 |
| B. FastAPI 模块化单体 + Temporal workers + Next.js | 清晰领域边界；复用 Python schema/adapter；worker 可独立扩容 | 两运行时、契约同步、Temporal 运维 | **推荐方向** |
| C. 按 Agent/Provider 拆微服务 | 独立扩容与故障域 | 两周 Mock 无法承担分布式事务、部署和契约复杂度 | 暂不推荐 |
| D. Serverless API + 托管工作流 | 运维较少 | FFmpeg 时长/磁盘限制、Provider 轮询、供应商锁定、成本不确定 | 仅作为部署 spike 候选 |

### 推荐逻辑

选择 B，但“独立进程”不等于“独立产品微服务”。API 只处理短请求和命令；Temporal workflow 只做确定性编排；Activity 执行 DB、Provider 与媒体副作用；媒体 worker 使用独立 task queue 限制 CPU/磁盘并发。

## 4.2 项目编排与 Shot Graph

**推荐：两层编排。**

1. **Project Workflow（控制平面）：** preflight → planning → bibles → shot plan → fan-out shot workflows → timeline/render → rough cut；接收 pause/resume/cancel/repair/selection 信号。
2. **Shot Workflow 或受控 child workflow（执行平面）：** keyframe → generation candidates → QC → bounded repair → approve/escalate。

不要让一个 Temporal workflow 承载完整领域真相。PostgreSQL 是用户可查询的业务事实来源；Temporal history 是执行恢复事实来源。二者通过稳定 ID 和带唯一键的 Activity 连接，不做双向“任意状态同步”。

**Shot Graph 推荐模型：**

- 节点是有版本的领域对象/资产需求，而不仅是镜头编号。
- 边至少区分 `EXECUTION_REQUIRES`、`DERIVED_FROM`、`CONTINUITY_REFERENCE`、`AUDIO_SYNC`、`INVALIDATES_ON_CHANGE`。
- Timeline 保存播放顺序；执行图必须可拓扑排序。
- 修改先在数据库事务内生成 impact plan；用户确认后创建新版本并提交 reconcile command，旧资产不可变但可标记 superseded。

**替代方案：** 把图完全编码在 Temporal history（查询与影响预览差）；把图完全当数据库队列（需自建 timers/retry/recovery）；使用通用图 Agent 框架（不解决付费副作用与媒体资产一致性）。推荐方案兼顾可查询与 durable execution。

## 4.3 状态机方向

**推荐：分层、单写者、转换有原因。**

- Project：用户可理解的聚合生命周期。
- Shot：镜头生产/审核生命周期。
- Job/ProviderAttempt：提交、已接受、运行、回调、对账、成功、失败、未知、取消。
- Asset：临时、已验证、选中、被替代、删除待处理。
- Issue/Review：open、auto-repairing、waiting-human、resolved、accepted-risk。

每次转换记录 `from/to/reason/actor/causation_id/correlation_id/version/time`。状态转换由领域服务校验，Temporal 不直接任意写状态；API 也不能越过命令入口改最终状态。UI 项目进度应从这些事实投影，而不是把 Temporal query 当唯一页面数据库。

**权衡：** 多个状态机会增加模型数量，但避免一个巨型枚举混合业务、执行、审核和控制语义。

## 4.4 长任务、幂等、重试与恢复

**推荐模式：at-least-once 执行 + 业务幂等 + Provider 对账，而不是声称 exactly-once。**

1. 每个逻辑副作用创建稳定 `operation_id`，由业务输入版本、任务类型、目标和策略版本决定；不得把每次 retry 的随机 ID 当幂等键。
2. PostgreSQL 对 `(workspace_id, operation_id)` 建唯一约束；先创建 operation/预算预留，再调用 Provider。
3. Provider 支持 idempotency key 时传同一 key；支持 client reference/query 时保存外部 job ID 并优先 reconcile。
4. 提交后响应丢失时进入 `SUBMISSION_UNKNOWN`；先按 key/query 对账。无法证明未提交时，绝不自动再次付费。
5. Provider 回调写入 inbox 表，以 provider event ID 或规范化 payload hash 去重；Activity 再消费并推进状态。
6. Asset 使用临时路径写完、校验、计算 hash 后原子发布；相同 operation 的重复结果不污染选中资产。
7. CostEvent 是 append-only 账本：estimate/reservation/actual/adjustment 分开；对 provider charge/reference 唯一。

Temporal Activity 默认可能重试，官方文档强调 Activity retry policy 和超时需要明确配置；Heartbeat 能报告进度并协助取消/恢复长 Activity。[Temporal Failure Detection](https://docs.temporal.io/develop/python/failure-detection) [Temporal Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies)

**重试分类：**

- 网络抖动、429、可恢复 5xx：指数退避、抖动、Provider rate limit；不消耗创意 repair budget。
- 认证、余额、内容拒绝、不支持输入：non-retryable，转 Issue。
- Provider job 仍运行：轮询/回调等待，不重提。
- 生成成功但 QC 失败：进入最多 2 次 repair cycle，每次产生新 operation/cost。
- FFmpeg 瞬时 worker 故障：可重试同一 deterministic operation；输入/工具版本相同则复用输出 hash。

## 4.5 Provider Adapter 架构

**推荐：能力接口而非一个万能 `generate()`。**

核心层使用标准命令/结果/错误，但按能力拆分，例如 image generation、video generation、TTS、lip-sync、music、moderation、VLM review。每个 Provider 发布 capability descriptor：输入模式、最大时长/尺寸、reference 数量、seed、区域、取消、callback、idempotency、查询、价格版本和内容限制。

适配器职责：

- 校验并映射标准请求；返回 provider request snapshot（脱敏）。
- 标准化 accepted/running/succeeded/failed/unknown 与错误分类。
- 提交、轮询、取消、回调验证、下载校验和成本解析。
- 暴露明确的能力差异；路由层只有在等价策略或用户批准后切换。

业务层职责：Shot route、预算、repair policy、选择和状态转换。Adapter 不应决定剧情，不直接改变 Shot 状态，也不把厂商字段扩散到核心表。

**图片/视频/音频集成风险：** 异步模式差异、临时 URL 过期、输出水印/codec 不一、中文标点与音素、声音授权、native audio 与独立 TTS 的时间绑定、seed 不保证复现、模型静默升级。所有真实 Provider 选择保持未决，使用 capability/contract test 比较。

## 4.6 资产存储

**推荐：** 开发期本地文件系统遵守 DEC-011，但从第一天通过 Storage Adapter 使用逻辑 key，例如 `workspaces/{workspace}/projects/{project}/assets/{asset}/{version}`；数据库只保存 storage URI/key、hash、size、media metadata、lineage 与状态。

- 原始资产和派生资产不可变；选择关系可变且版本化。
- 同一文件系统上的临时写入 + fsync/rename 后发布；PostgreSQL 事务记录发布结果。
- 浏览器不接受任意服务器路径；API 返回短期受控下载入口。
- FFmpeg 在每任务 scratch directory 工作，限定磁盘配额并清理。

**替代方案：** 直接绝对路径最快但阻塞 S3 迁移；Mock 即使用 MinIO 更接近对象存储但增加两周里程碑运维。先本地 adapter，随后用相同 contract test 验证 S3/OSS。

## 4.7 Cost 与 Evidence tracking

**Cost 推荐：** append-only CostEvent + BudgetReservation。付费前在数据库原子检查 `actual + active_reservations + next_upper_bound <= approved_limit`，以整数最小货币单位存储；调用后用 actual 调整 reservation。并发镜头不能各自只读取余额。

**Evidence 推荐：** EvidenceManifest 是可导出的派生索引，不是日志/大文件的第二份复制。每项包含 subject、type、source URI、content hash、schema/tool/model version、产生时间、actor、correlation/causation ID 和验证结果。敏感 Provider request 保存脱敏快照；密钥、authorization header、临时签名 URL 永不进入 Evidence。

**替代方案：** 只从日志重建成本/Evidence 简单但不可审计；事件溯源所有领域数据过重。针对成本、转换与 Evidence 使用 append-only records，其他业务实体保持常规版本表，是更小的方案。

## 4.8 实时进度