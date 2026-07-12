# Factory OS — AI-Native Factory Decision Hub

> Built by 1 person + AI coding tools + ~¥500/month API cost.
> Traditional approach: millions in software fees, a team, 6 months.
> This approach: 6 months, ¥500/month, 1 person.

## What is this?

Factory OS is an AI-native operating system for ETO (Engineer-to-Order) factories. Not another MES. Not an ERP wrapper. It's a decision hub where AI is not a plugin — it's the system kernel.

**Current status:** Running in production at one ETO factory. 20+ workers use the Copilot Widget daily for natural-language work reporting.

## Architecture

```
ERP (IN3 API) / MES / Excel / DingTalk
              │
     ┌────────┴────────┐
     │  KNOWLEDGE LAYER │  Ontology engine (8 objects + 5 relations)
     │  MEMORY SYSTEM   │  4 types: decision / correction / pattern / context
     │  AGENT FRAMEWORK │  IntentRouter → ReactAgent → 8 primitive tools
     │  PERMISSION      │  L0 read-only / L1 confirmed write / L2 auto
     │  ACTION EXECUTOR │  Saga compensation + SQL sandbox + IM streaming cards
     │  COPILOT-FIRST UI│  "Chat is the interface" — Next.js 15, shadcn/ui
     └─────────────────┘
```

## Key Design Decisions

### 1. Tool Calling: 40+ semantic tools → 8 primitives

Why? New requirement = new tool = new code + new tests + new prompts. Doesn't scale.

The 8 primitives (inspired by Claude Code's 6-tool philosophy):
`query_data` | `aggregate_data` | `search_entities` | `read_file` | `execute_write` | `call_api` | `send_message` | `schedule_task`

LLMs are better at composing tools than we think.

### 2. Memory: Not chat history. Learning data.

| Type | What it stores | Purpose |
|---|---|---|
| Decision Memory | Human approval/rejection of AI suggestions | Next suggestion better matches human preference |
| Correction Memory | AI mistakes + human corrections | Never repeat the same mistake |
| Pattern Memory | Discovered patterns (e.g., "efficiency drops every Friday afternoon") | Proactive alerts |
| Context Memory | Human-annotated flags (e.g., "WO-001 is the boss's personal project") | Priority differentiation |

### 3. Permission: 3-tier, not 2-tier

| Level | Capability | Trigger |
|---|---|---|
| L0 | Read-only queries | Default, no confirmation |
| L1 | Parameterized writes | Show operation → human clicks confirm |
| L2 | Fully automated | Pre-registered tasks only, cannot dynamically upgrade |

Why 3? 2-tier (read/write) means parameterized writes like "change the estimated completion date" get stuck in approval queues → system becomes decoration.

### 4. Action Executor + Saga Compensation

Multi-step operations need transaction guarantees. Each `execute_write` requires a `reverse` definition. If any step fails, roll back completed steps in reverse order using `field_history` to auto-generate reverse SQL.

### 5. SQL Sandbox

3-layer defense: sqlglot AST whitelist → runtime resource limits (statement_timeout, row_limit) → EXPLAIN cost guard.

## Tech Stack

`Python` `FastAPI` `Next.js 15` `React 19` `PostgreSQL 16` `Neo4j 5` `Docker Compose` `MCP SDK` `Playwright` `shadcn/ui` `Tailwind CSS`

## Git History (70 commits, May–Jun 2026)

Selected milestones:

```
2026-05-19  First commit — standard time calculator
2026-06-09  Factory agent with tool registry + workflow engine + teaching mechanism
2026-06-24  Phase 0: Deleted all Streamlit files → Next.js refactor begins
2026-06-25  Phase 1-2: FastAPI skeleton + Priority Engine + Command Center
2026-06-25  Phase 3-4: 4 business centers + Data Hub + Settings
2026-06-25  Phase 5-6: AI nervous system (Cmd+K / auto-push / decision history) + Docker deploy
2026-06-26  Phase 7a: 8 basic primitives + SQL sandbox (AST + Cost Guard + Row Guard)
2026-06-26  Phase 7b: RiskEngine — 3-tier risk grading + confidence→quality mapping
2026-06-26  Phase 7c: ActionExecutor — Saga compensation + optimistic lock rollback
2026-06-29  Personnel dashboard rewrite + Phase 0-6 review fixes + Phase 7 docs
```

## Author

**Zhu Shuai** — Former IE engineer, digital transformation consultant, AI-native builder. Applying to DeepSeek AI Cross-Disciplinary Talent / Agent Harness PM.

- 1999.08 | 13236301160 | 531016954@qq.com
- Available from 2026.08.01

## License

This repository is a demo/portfolio version. Production code contains client factory data and cannot be fully open-sourced. Architecture diagrams, design documents, and sanitized core modules are available in the [docs](./docs) directory.
