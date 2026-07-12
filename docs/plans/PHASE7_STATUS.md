# Phase 7 实施状态

> 更新：2026-06-29 | 下一步：Phase 7d-7f

---

## 已完成 (7a-7c) ✅

| Phase | Task | Commit | 测试 |
|-------|------|--------|------|
| 7a-1 | DDL 迁移 v2 — updated_at + im_* + scheduled_tasks | `c8298dc` | 3/3 PASS |
| 7a-2 | SQL 安全沙箱 — AST + Cost Guard + Row Guard | `068fcd8` | 41/41 PASS |
| 7a-3 | 8 个基础原语 | `de2069d` | 10/10 PASS |
| 7a-4 | 3 个语义快捷方式 | `2aa60d9` | 3/3 PASS |
| 7b-1 | RiskEngine — L0/L1/L2 + 置信度映射 | `bb664cf` | 20/20 PASS |
| 7b-2 | ActionPlan + ActionDispatcher | `a7ff99c` | 6/6 PASS |
| 7c-1 | ActionExecutor — Sagas 补偿 + 乐观锁 | `374b489` | 5/5 PASS |

## 待完成 (7d-7f) ⏳

阻塞原因：需要钉钉开发者凭证（ClientID + ClientSecret）才能测试 Stream 模式。

| Phase | 内容 | 依赖 |
|-------|------|------|
| 7d | IM 适配器 + 钉钉 Stream 集成 | 钉钉 App 凭证 |
| 7e | IM 配对授权 + 前端设置页 | 7d |
| 7f | 联调 + 流式进度卡片 + 端到端测试 | 7a-7e |

## 待办 Checkpoint

### 恢复开发时需要做的事：

1. **准备钉钉凭证**
   - 在[钉钉开放平台](https://open.dingtalk.com)创建机器人应用
   - 获取 ClientID + ClientSecret
   - 配置到 `.env`：`DINGTALK_CLIENT_ID=xxx` `DINGTALK_CLIENT_SECRET=xxx`

2. **读这个文件了解当前状态** ← 你就在这里

3. **执行 Phase 7d** — 参考设计文档 §6：
   - 创建 `core/im/base.py` (IMessage + MessageAdapter ABC)
   - 创建 `core/im/dingtalk.py` (DingTalkAdapter)
   - 创建 `core/im/pairing.py` (配对授权)
   - 创建 `api/routers/im.py` (IM webhook + 平台管理 API)
   - 创建 `api/models/im.py` (IM ORM 模型)
   - 修改 `api/main.py` 注册 IM router

4. **执行 Phase 7e** — 前端 IM 管理 + QualityIndicator

5. **执行 Phase 7f** — 联调流式进度卡片

### 接口契约（7d-7f 开发时用）：

- `core/im/base.py`: `MessageAdapter` ABC exposes `start/stop/send_text/send_card/update_card`
- `core/agent/tools/primitives.py:_send_message` 目前是桩（返回 warning），Phase 7d 替换为真实调用
- `api/routers/im.py` 端点: `POST /api/im/dingtalk/webhook`, `GET/POST /api/im/platforms`
- `api/models/im.py` 表: `im_platforms`, `im_authorized_users`, `im_pairing_codes` (DDL 已在 7a-1 创建)

## 新增文件总览

```
core/
├── agent/
│   ├── sql_sandbox.py          ← SQL 三级防护
│   ├── tools/
│   │   ├── primitives.py       ← 8 个基础原语
│   │   └── shortcuts.py        ← 3 个快捷方式
│   ├── risk_engine.py          ← L0/L1/L2 风险判定
│   ├── action_plan.py          ← ActionPlan 数据结构
│   └── action_dispatcher.py    ← 执行意图分发
│
api/
└── services/
    └── action_executor.py      ← Sagas 补偿执行器

tests/
├── test_agent/
│   ├── test_sql_sandbox.py
│   ├── test_primitives.py
│   ├── test_shortcuts.py
│   ├── test_risk_engine.py
│   └── test_action_dispatcher.py
└── test_action_executor.py
```
