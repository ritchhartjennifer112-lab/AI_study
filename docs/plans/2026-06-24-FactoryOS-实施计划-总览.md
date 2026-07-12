# Factory OS 完整实施计划 — 总览

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 每个 Task 由一个独立的 subagent 执行，执行前先读取：
> 1. 本总览文件（了解架构和上下文）
> 2. 对应阶段的实施文件（如 `Phase1-Backend.md`）
> 3. `docs/plans/2026-06-24-FactoryOS-DataModel.md`（数据模型定义）

---

## 项目概况

**目标：** 将现有 Streamlit 工厂管理系统（21 个页面）重构为 Next.js 15 + FastAPI 的 Factory OS，保留 core/*.py 全部业务逻辑，新增 Priority Engine / Event Pipeline / Decision Center 等核心能力。

**工期估算：** 20-22 天（单人开发）
**工作负载：** 前端 40% / 后端 60%

---

## 阶段总览

| Phase | 名称 | 天数 | 产出 | 依赖 | 实施文件 |
|-------|------|------|------|------|---------|
| 0 | Design System + 项目脚手架 | 5 | Next.js 项目 + 完整组件库 + shadcn/ui | 无 | [Phase0](2026-06-24-FactoryOS-Phase0-DesignSystem.md) |
| 1 | 后端骨架 + Priority Engine | 5 | FastAPI + 5 张 DB 表 + Event Pipeline + 评分引擎 | Phase 0（前端依赖） | [Phase1](2026-06-24-FactoryOS-Phase1-Backend.md) |
| 2 | 指挥中心 | 3 | Decision Center 首页 + AI Context Strip | Phase 1（API 依赖） | [Phase2](2026-06-24-FactoryOS-Phase2-CommandCenter.md) |
| 3 | 业务中心 | 4 | 生产/设备/人员/物料 4 个页面 | Phase 0 + Phase 1 | [Phase3](2026-06-24-FactoryOS-Phase3-BusinessCenters.md) |
| 4 | 数据中枢 + 设置 | 3 | 因果分析/来源追溯/数据同步/系统设置 | Phase 3 | [Phase4](2026-06-24-FactoryOS-Phase4-DataHub.md) |
| 5 | AI 神经系统 | 3 | Context Strip 全页面生效 + Cmd+K + 决策跟踪 | Phase 2 + Phase 3 | [Phase5](2026-06-24-FactoryOS-Phase5-AI.md) |
| 6 | 收尾 | 2 | 响应式/错误态/部署配置 | 全部 | [Phase6](2026-06-24-FactoryOS-Phase6-Polish.md) |

---

## 新项目目录结构

```
d:\AI知识库\AI++++\工厂现场——工时\
│
├── api/                          # FastAPI 后端（NEW）
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # 配置管理
│   ├── dependencies.py           # JWT + DB 依赖注入
│   ├── models/                   # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── event.py
│   │   ├── decision.py
│   │   ├── insight.py
│   │   ├── action.py
│   │   └── notification.py
│   ├── domain/                   # 领域逻辑
│   │   ├── __init__.py
│   │   ├── priority_engine.py    # L1-L5 评分引擎
│   │   └── context_filter.py     # 语境过滤
│   ├── services/                 # 编排层
│   │   ├── __init__.py
│   │   ├── event_service.py
│   │   ├── decision_service.py
│   │   └── notification_service.py
│   └── routers/                  # FastAPI 路由
│       ├── __init__.py
│       ├── auth.py
│       ├── events.py
│       ├── decisions.py
│       ├── context_strip.py
│       ├── actions.py
│       └── business.py           # 工单/员工/设备/物料/效率
│
├── frontend/                     # Next.js 15（NEW）
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── components.json           # shadcn/ui 配置
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx        # 全局布局
│   │   │   ├── page.tsx          # 指挥中心（Decision Center）
│   │   │   ├── globals.css       # 全局样式
│   │   │   ├── production/       # 生产中心
│   │   │   ├── equipment/        # 设备中心
│   │   │   ├── personnel/        # 人员中心
│   │   │   ├── materials/        # 物料中心
│   │   │   ├── data/             # 数据中枢
│   │   │   └── settings/         # 系统设置
│   │   ├── components/
│   │   │   ├── ui/               # shadcn/ui 组件
│   │   │   ├── app-shell.tsx     # 全局布局壳
│   │   │   ├── sidebar.tsx       # 侧边栏导航
│   │   │   ├── topbar.tsx        # 顶部栏
│   │   │   ├── page-header.tsx   # 页面标题
│   │   │   ├── decision-card.tsx # 决策卡片
│   │   │   ├── insight-card.tsx  # 洞察卡片
│   │   │   ├── context-strip.tsx # AI 上下文条
│   │   │   ├── kpi-card.tsx      # KPI 指标卡
│   │   │   ├── data-table.tsx    # 数据表格
│   │   │   ├── status-badge.tsx  # 状态指示器
│   │   │   └── empty-state.tsx   # 空态
│   │   ├── lib/
│   │   │   ├── api.ts            # API 客户端
│   │   │   └── utils.ts          # 工具函数
│   │   └── types/
│   │       └── index.ts          # TypeScript 类型
│   └── public/
│
├── core/                         # 保留，原业务逻辑（不变）
│   ├── delivery_risk.py
│   ├── ontology_engine.py
│   ├── production_risk.py
│   ├── dispatch_suggester.py
│   ├── inbox_ai.py
│   ├── skill_matrix.py
│   ├── database.py
│   ├── erp_sync.py
│   ├── erp_integration.py
│   ├── deviation.py
│   ├── personnel_*.py
│   ├── agent/                    # 保留 AI Agent 层
│   └── ...
│
└── docs/plans/
    ├── 2026-06-24-FactoryOS-DataModel.md     # 数据模型定义（已存在）
    ├── 2026-06-24-FactoryOS-NextJS-重构方案.md # 方案设计（已存在）
    ├── 2026-06-24-FactoryOS-实施计划-总览.md   # 本文件
    ├── 2026-06-24-FactoryOS-Phase0-DesignSystem.md
    ├── 2026-06-24-FactoryOS-Phase1-Backend.md
    ├── 2026-06-24-FactoryOS-Phase2-CommandCenter.md
    ├── 2026-06-24-FactoryOS-Phase3-BusinessCenters.md
    ├── 2026-06-24-FactoryOS-Phase4-DataHub.md
    ├── 2026-06-24-FactoryOS-Phase5-AI.md
    └── 2026-06-24-FactoryOS-Phase6-Polish.md
```

---

## 阶段启动顺序

```
Phase 0 (Design System)
  │
  ├──→ Phase 1 (Backend)           ← 可以并行，但 Phase 1 API 先于 Phase 2
  │       │
  │       └──→ Phase 2 (Command Center)  ← 依赖 Phase 1 API + Phase 0 组件
  │               │
  │               └──→ Phase 3 (Business Centers)
  │                       │
  │                       └──→ Phase 4 (Data Hub)
  │                               │
  │                               └──→ Phase 5 (AI)
  │                                       │
  │                                       └──→ Phase 6 (Polish)
```

**并行策略：** Phase 0 和 Phase 1 可以同时进行（前后端解耦开发）。Phase 2 开始需要两个都完成。

---

## 关键约定

### commit 规范

```
feat: [Phase N] 完成 XXX 功能
fix: [Phase N] 修复 XXX 问题
docs: 更新文档
chore: 构建/工具链变更
```

### 代码风格

- Python：Black 格式化，类型注解，Google-style docstring
- TypeScript：Prettier，2 空格缩进，箭头函数组件
- 数据库：SQLite 开发，PostgreSQL 生产（ORM 用 SQLAlchemy 2.0）

### 数据模型引用

所有 Pydantic 模型定义见 `docs/plans/2026-06-24-FactoryOS-DataModel.md`。本计划的 Task 不再重复定义模型，只写实现代码。

---

## 环境准备（所有 Phase 前提）

```bash
# Python 环境
cd d:/AI知识库/AI++++/工厂现场——工时
python -m venv .venv
source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt] pydantic

# Node.js 环境
# 确保 Node >= 18
node --version
```
