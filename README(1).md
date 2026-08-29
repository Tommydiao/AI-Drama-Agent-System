# AI 短剧制作 Agent — 项目文档包 v0.1

## 文件状态

| 文件 | 状态 |
|---|---|
| `INTENT.md` | Approved — Baseline Locked |
| `02_DECISIONS.md` | Approved |
| `03_PRODUCT_SPEC.md` | Draft for Product Review |
| `04_USER_FLOWS.md` | Draft for Product Review |

## 推荐放置方式

将四份文件放入新建的私有仓库根目录：

```text
ai-short-drama-agent/
├── INTENT.md
├── 02_DECISIONS.md
├── 03_PRODUCT_SPEC.md
└── 04_USER_FLOWS.md
```

## 建议 Git 提交

```bash
git add INTENT.md 02_DECISIONS.md 03_PRODUCT_SPEC.md 04_USER_FLOWS.md
git commit -m "docs: establish intent decisions product spec and user flows"
git tag product-foundation-v0.1
```

## 当前研发阶段

```text
Stage 0 — INTENT: Approved
Stage 1 — DECISIONS: Approved
Stage 2 — PRODUCT SPEC / USER FLOWS: Draft for Review
Stage 3 — EXPLORE / ARCHITECTURE: Not Started
Stage 4 — DATA CONTRACTS / STATE MACHINES: Not Started
Stage 5 — IMPLEMENTATION PLAN: Not Started
Stage 6 — BUILD: Not Started
```

## 下一 Gate

Product Owner 审核 `03_PRODUCT_SPEC.md` 和 `04_USER_FLOWS.md` 后：

1. 锁定产品规格与用户流程。
2. 向 Codex 下发 Explore-only 指令。
3. 基于 Explore Evidence 生成：
   - `05_ARCHITECTURE.md`
   - `06_DATA_CONTRACTS.md`
   - `07_STATE_MACHINES.md`
   - `08_PROVIDER_SPEC.md`
   - `09_EVALUATION_SPEC.md`
   - `10_SECURITY_AND_RIGHTS.md`
4. 架构通过后再编写实施计划，不直接进入业务编码。
