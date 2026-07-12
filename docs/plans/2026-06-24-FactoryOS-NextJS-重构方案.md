# Factory OS 完整重构方案 v4

> **核心变更：** v3 → v4 新增 [Factory Intelligence Data Model](2026-06-24-FactoryOS-DataModel.md)（Event/Decision/Insight/Action/Notification 五对象完整定义），Priority Engine 明确为纯规则引擎（非 AI 引擎），新增 Decision History 追踪，Context Filter 明确为后端服务，工作负载修正为 **40% 前端 / 60% 后端**。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**核心原则:** 不是把 Streamlit 翻译成 Next.js。是在保留业务逻辑的前提下，重新设计产品。

**资产保留清单（一个字不改）:**

```
core/*.py            → 业务逻辑全保留
core/agent/*         → AI Agent 全保留
core/db.py           → 数据库连接
core/delivery_risk   → 交付风险评估
core/production_risk → 生产风险
core/dispatch_suggester → 派工建议引擎
core/ontology_engine → 本体推理
core/inbox_ai        → 收件箱AI分类
core/skill_matrix    → 技能矩阵
core/database.py     → 数据访问层
core/erp_*.py        → ERP同步
core/personnel_*     → 人员管理
core/deviation.py    → 效率偏差计算
config/ontology.json → 本体定义
```

**资产删除清单（立即删除，不兼容）:**

```
app.py               → 首页
pages/*              → 全部22个页面
core/auth.py         → Streamlit 认证（替换为 JWT）
core/agent/copilot_widget.py  → Streamlit Copilot（替换为独立组件）
.streamlit/config.toml        → Streamlit 配置
```

**技术栈:**

| 层 | 技术 |
|---|---|
| 前端框架 | Next.js 15 (App Router) |
| 样式 | Tailwind CSS v4 |
| 组件库 | shadcn/ui |
| 图表 | Recharts |
| 表格 | @tanstack/react-table |
| 表单验证 | zod + react-hook-form |
| 后端 | FastAPI |
| 认证 | JWT (python-jose) |
| 部署 | Docker |

---

## 一、产品架构（不是页面架构）

### 1.0 核心引擎: Factory Intelligence Priority Engine

这是整个系统的**神经中枢**，不是某一个页面。它做的事情：

```
输入: 原始事件（缺勤、缺料、延期、异常...）
  │
  ▼
ontology_engine.trace()  → 计算影响范围（谁/什么会被影响）
delivery_risk.calc()     → 评估严重程度
  │
  ▼
三级过滤:
  事件        张三请假
    ↓
  影响        A线缺少1名冲压工
    ↓
  决策        是否调配李强补位？
  │
  ▼
L1-L5 分级（见 1.1）
  │
  ▼
分角色投递（见 1.2）
```

**这个引擎不在 Phase 4 做，是 Phase 1 就要做。** 因为首页（指挥中心）的内容完全依赖这个引擎的输出。

#### 1.0.1 消息等级体系

所有消息必须经过价值评估才能展示，禁止模块直接发消息到首页。

等级内加 **score (0-100)** 细粒度优先级，同 level 内按 score 降序排列。

| 等级 | 定义 | score 范围 | 展示方式 | 有效期 |
|---|---|---|---|---|
| **L1 信息** | 正常操作记录：张三打卡、工单开始、设备启动 | 0-20 | 仅记录到 DB，不主动推送 | — |
| **L2 提醒** | 需要注意但不紧急：库存低于预警线、设备保养到期 | 21-50 | AI Context Strip 对应负责人可见 | 24h |
| **L3 风险** | 可能出问题：延期概率 > 60%、缺料影响生产 | 51-75 | AI Context Strip 主管↑可见 | 至解决 |
| **L4 决策** | 必须有人做决定：调整排产、采购审批、加班审批 | 76-90 | Decision Center 首页主区域 | 至决策 |
| **L5 经营影响** | 影响客户/利润/产值 | 91-100 | Decision Center 顶部 + 厂长首页 | 至解决 |

**score 决定展示顺序。** 同是 L3：库存预警 score=52 排在后，WO-1827 延期 80% score=88 排在前。

**置信度影响等级。** 事件携带 `confidence`（来源可信度），引擎据此调整最终 level：
- ERP 确认事件 confidence >= 0.95 → 按实际等级展示
- AI 推理事件 confidence < 0.7 → 降一级展示（L3 当 L2 展示）
- 多来源冲突 → 取高 confidence + 打上 `conflict` 标记

**示例:**

```
事件: 张三请假
→ ontology_engine.trace("张三") → 关联 A线、冲压工位、WO-1827
→ 影响分析: A线产能下降5%，WO-1827可能延期
→ 等级判定: L3（影响生产风险）
→ 分角色:
   - 班组长: L3 "A线冲压工位缺1人，建议调配李强补位"
   - 车间主任: L3 "A线产能预计下降5%，WO-1827延期风险"
   - 厂长: L4 "WO-1827预计延期影响客户交付，需确认是否加急"
```

#### 1.0.2 三级过滤

```
事件层      张三请假、库存告警、设备停机...
              ↓  ontology_engine.trace()
影响层      A线缺人、缺料影响3个工单、E-0045停机...
              ↓  priority_engine.assess()
决策层      是否补位？是否调整排产？是否批准采购？
              ↓  context_filter(role, current_page, current_focus)
投递        Decision Center / AI Context Strip / 数据记录
```

**设计原则：** 用户首页看到的是"决策层"，不是"事件层"。AI Context Strip 展示的是"影响层"，不是"事件层"。

#### 1.0.3 Factory Context Filter（角色 + 语境双维度）

系统预置三种角色，但同一个人的关注点会随页面切换而变化。因此过滤维度从单一 `role` 升级为 `context`：

```python
class UserContext(BaseModel):
    role: str            # "operator" | "supervisor" | "admin"
    current_page: str    # "production" | "equipment" | "personnel" | "materials"
    current_focus: str   # 可选, 如 "WO-1827", "E-0045" (从当前页面 URL/操作推断)
```

**效果：**

```
同一个人(admin)在不同页面看到不同的 Context Strip:

进入 /production → "⚠ WO-1827 延期风险 82% · 影响产值 ¥126,000"
进入 /personnel  → "⚠ 关键岗位焊工缺勤 2 人 · A线产能受影响"
进入 /materials  → "⚠ A料库存不足 · 已影响 3 个工单"

不是永远看到同一批消息，而是语境决定优先级。
```

---

### 1.1 领域划分（v2 更新版）

```
┌────────────────────────────────────────────────────────────┐
│                     AI Context Strip                        │
│  每页顶部 40px，一行文本 + 操作链接                           │
│  只展示 L2-L3，且只展示当前角色相关的                           │
│  厂长看生产中心: "⚠ WO-1827 预计延期影响 ¥126,000"            │
│  班组长看生产中心: "⚠ 今日缺勤 2 人，冲压工位缺1人"            │
├────────────────────────┬───────────────────────────────────┤
│    Decision Center     │   — 所有 L4-L5 消息统一入口         │
│    ┌──────────────┐    │   — 首页主区域（取代仪表盘）         │
│    │ 待决策 5项    │    │   — 按 context(role+page) 过滤     │
│    │ ──────────── │    │   — 按 level DESC + score DESC 排序│
│    │ 延期风险 × 3 │    │                                     │
│    │ 采购审批 × 2 │    │  生产中心（/production）             │
│    └──────────────┘    │  人员中心（/personnel）              │
│                        │  物料中心（/materials）              │
│    右上角:             │                                     │
│    Factory Index       │  数据中枢（/data）                   │
│    仅作参考指标        │  系统设置（/settings）                │
├────────────────────────┴───────────────────────────────────┤
│  无 /intelligence/copilot 路由                              │
│  Cmd+K 全局命令面板（不是页面，是覆盖层）                      │
└────────────────────────────────────────────────────────────┘
```

### 1.2 路由设计（v2 更新版）

```
/                    → 指挥中心 (Decision Center)
                       第一屏: L4-L5 决策项（按 level DESC + score DESC）
                       第二屏: AI Context Strip（L2-L3 当前语境相关）
                       右上角: Factory Index（小字号，参考指标）

/production          → 生产中心
/equipment           → 设备中心
/personnel           → 人员中心
/materials           → 物料中心

/data                → 数据中枢
/settings            → 系统设置

无 /intelligence/copilot 路由
无独立 AI 页面
```

### 1.3 四层后端架构

```
┌───────────────────────────────────────────────┐
│  api/routers/                                 │
│  FastAPI 路由层，只做三件事:                     │
│  1. 解析 HTTP 请求                             │
│  2. 调用 domain 层                             │
│  3. 返回 JSON                                  │
├───────────────────────────────────────────────┤
│  api/domain/                                  │
│  领域层，聚合多个 service 完成一个业务用例         │
│  新增: priority_engine.py  ← 核心引擎，含分级+打分   │
│  新增: context_filter.py   ← 语境感知过滤            │
├───────────────────────────────────────────────┤
│  api/services/                                │
│  编排层，调用 core/*.py，处理缓存/事务/重试       │
├───────────────────────────────────────────────┤
│  core/*.py                                    │
│  原始业务逻辑，完全不变                          │
└───────────────────────────────────────────────┘
```

---

## 二、Factory Intelligence Priority Engine（核心新增）

这是 v2 方案最重要的新增内容。它不是一个 API、不是一个页面，是一个**领域层的消息价值评估引擎**。

### 2.1 输入

```python
class RawEvent(BaseModel):
    type: str         # "absent", "shortage", "delay", "breakdown", "overtime"...
    entity_id: str    # "张三", "E-0045", "WO-1827"...
    entity_type: str  # "employee", "equipment", "order"
    detail: str
    timestamp: str
    source: str       # "erp_sync" | "excel_import" | "inbox_ai" | "agent_inference" | "manual"
    confidence: float # 0.0 - 1.0，来源可信度
    metadata: dict = {}  # 预留扩展
```

**source + confidence 的作用：**

| source | 典型 confidence | 说明 |
|---|---|---|
| `erp_sync` | 0.95-1.0 | ERP 系统直连，高可信 |
| `excel_import` | 0.85-0.95 | Excel 导入，可能有格式误差 |
| `inbox_ai` | 0.60-0.90 | AI 文件分类，中可信 |
| `agent_inference` | 0.40-0.80 | Agent 推理，低可信 |
| `manual` | 1.0 | 手动录入 |

置信度影响引擎展示：
- ERP 确认事件 (conf >= 0.95) → 按实际等级展示
- AI 推理事件 (conf < 0.70) → 降一级展示（L3 按 L2）
- 多来源冲突 → 取高 conf + 标记 `conflict`
- 低 conf 不产生 L4-L5 决策（避免"AI 怀疑延期"出现在首页）

### 2.2 引擎工作流

```python
class PriorityEngine:
    def process(self, event: RawEvent, user_context: UserContext) -> list[PrioritizedMessage]:
        # Step 1: 通过 ontology 追溯影响范围
        impacts = ontology_engine.trace(
            entity_id=event.entity_id,
            entity_type=event.entity_type,
        )

        # Step 2: 评估严重程度 + 经济损失
        for impact in impacts:
            impact.economic_loss = delivery_risk.estimate_loss(
                impact.entity, event.type
            )

        # Step 3: 判定基础等级 (L1-L5) + 初始 score
        level, base_score = self._determine_level_and_score(event, impacts)

        # Step 3b: 根据置信度调整等级
        if event.confidence < 0.5:
            level = max(1, level - 2)  # 跳两级的低可信事件
        elif event.confidence < 0.7:
            level = max(1, level - 1)  # 降一级
        # >= 0.95 保持原等级

        # Step 3c: 最终 score = base_score * confidence
        final_score = round(base_score * event.confidence)

        # Step 4: 按语境 (role + current_page) 生成消息
        messages = []
        for role_config in self._get_relevant_roles(user_context):
            msg = self._format_for_context(
                event=event,
                impacts=impacts,
                level=level,
                score=final_score,
                user_context=user_context,
            )
            if msg:
                messages.append(msg)

        # 返回结果按 level DESC + score DESC 已排序
        return sorted(messages, key=lambda m: (m.level, m.score), reverse=True)
```

### 2.3 输出

```json
{
  "level": 3,
  "score": 74,
  "role": "supervisor",
  "context": {
    "current_page": "production",
    "current_focus": ""
  },
  "raw_event": "张三请假",
  "source": "daily_report",
  "confidence": 0.97,
  "impacts": [
    { "entity": "A线", "type": "production_line", "effect": "缺少冲压工" },
    { "entity": "WO-1827", "type": "work_order", "effect": "产能下降5%" }
  ],
  "decision_required": false,
  "suggested_action": "调配李强补位冲压工位",
  "display": {
    "inbox": false,
    "strip": true,
    "strip_text": "A线冲压工位缺1人 · 建议调配李强补位"
  }
}
```

### 2.4 与现有系统的关系

```
core/delivery_risk.py  ──→  提供风险评分
core/ontology_engine.py ──→  提供实体关系追溯
core/production_risk.py ──→  提供生产风险评估
         ↓
api/domain/priority_engine.py  ← 新增，聚合三者
         ↓
api/services/notification_service.py  ← 新增，负责投递
```

---

## 三、Decision Center（核心新增）

### 3.1 概念

Decision Center 不是"邮件收件箱"，也不是"消息通知中心"。它是**所有 L4-L5 决策项的单一入口。**
- AI 发现风险 → 进入 Decision Center
- 主管确认调整 → 记录在 Decision Center
- 厂长回头看今天做了什么决定 → 去 Decision Center 查

排序规则: **level DESC + score DESC**。同一个 L4 内，score 88 排 score 76 前面，确保最紧急的决策排最上面。

### 3.2 数据结构

```json
{
  "id": "dc-20260624-001",
  "level": 4,
  "score": 88,
  "type": "risk",
  "title": "WO-1827 预计延期 2 天",
  "description": "铜牌仓B项目当前进度62%，交期剩余3天。预计影响客户交付，涉及金额 ¥126,000。",
  "status": "pending",
  "suggested_actions": [
    { "label": "批准加急", "action": "expedite", "payload": {"order_id": "WO-1827"} },
    { "label": "调整排产", "action": "reschedule", "payload": {"order_id": "WO-1827"} },
    { "label": "忽略", "action": "dismiss", "payload": {} }
  ],
  "source": "delivery_risk",
  "confidence": 0.92,
  "created_at": "2026-06-24T08:00:00Z",
  "resolved_at": null,
  "resolved_by": null,
  "decision": null
}
```

### 3.3 首页展示

```
┌─────────────────────────────────────────────────────────────┐
│  今天需要你决定 5 件事                                        │
│                                                             │
│  ┌─ L4 ─────────────────────────────────────────────────┐  │
│  │ 延期风险 │ WO-1827 铜牌仓B 预计延期2天               │  │
│  │ 影响客户交付 · 涉及金额 ¥126,000                     │  │
│  │                                    [批准加急] [忽略] │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ L4 ─────────────────────────────────────────────────┐  │
│  │ 采购审批 │ A料库存不足 · 已影响3个工单               │  │
│  │ 建议优先采购 · 预计 ¥8,500                          │  │
│  │                                    [批准采购] [忽略] │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ L3 ─────────────────────────────────────────────────┐  │
│  │ 人员调整 │ A线缺1名冲压工 · 建议调配李强补位        │  │
│  │                                    [确认] [忽略]    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  右上角: Factory Index 82 · 运行正常                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、阶段计划（v2 重排）

### Phase 0: Design System（不变，但不再提 Storybook）

**目标:** 建立完整的组件库，后续所有页面用组件拼装。

**时间:** 第一周，只做组件，不做页面。

**组件清单:**

| 组 | 组件 | 用途 |
|---|---|---|
| 布局 | AppShell, Sidebar, TopBar, PageHeader | 全局结构 |
| 数据 | DataTable, StatusBadge, RiskBadge, EmptyState | 数据展示 |
| KPI | KPICard, KPIRow | 指标卡片 |
| 卡片 | DecisionCard, InsightCard | 决策/洞察展示 |
| 图表 | BarChart, LineChart, AreaChart, GanttChart | 数据可视化 |
| AI | ContextStrip, InsightChip | AI 上下文条 |
| 表单 | WorkReportForm, DateRangePicker | 交互入口 |

---

### Phase 1: 后端骨架 + Priority Engine（重排）

**目标:** 优先建立整个系统的数据中枢，不是先做页面。

**Time:** 3 天

#### Task 1.1: FastAPI 基础

- `api/main.py` — 应用入口
- `api/config.py` — 配置
- `api/dependencies.py` — JWT + DB 依赖
- `api/routers/auth.py` — 认证

#### Task 1.2: Priority Engine（核心！）

- `api/domain/priority_engine.py` — L1-L5 分级 + score 打分引擎
- `api/domain/context_filter.py` — 角色 + 当前页面 + 当前焦点的语境过滤
- `api/services/notification_service.py` — 消息投递服务（分发到 Decision Center / Context Strip / 数据记录）
- `api/routers/decision_center.py` — Decision Center API

**API 契约:**

```
GET /api/decision-center?role=admin&page=production&level_min=4
→ 厂长在生产中心看到的 L4-L5 决策项（按 level DESC + score DESC 排序）

GET /api/decision-center?role=operator&level_min=2
→ 班组长首页看到的 L2-L3 提醒

POST /api/events
Body: { type, entity_id, entity_type, detail, source, confidence, ... }
→ 任何模块通过此接口推送原始事件
→ Priority Engine 自动分级 + 打分 + 投递

GET /api/context-strip?page=production&role=supervisor
→ 生产中心的 AI Context Strip 内容（只返回 L2-L3，按 score 降序限 3 条）
```

#### Task 1.3: 业务 API（只读优先）

为所有业务中心提供只读 API，让 Phase 2 的页面可以直接调用：

- `api/routers/work_orders.py` — 工单 API
- `api/routers/employees.py` — 员工 API
- `api/routers/equipment.py` — 设备 API
- `api/routers/materials.py` — 物料/缺料 API
- `api/routers/efficiency.py` — 效率 API
- `api/routers/personnel.py` — 人员 API

---

### Phase 2: 指挥中心（重排）

**目标:** 首页 = Decision Center（L4-L5）+ AI Context Strip（L2-L3）+ 快捷入口。不做仪表盘。

**Time:** 2 天

#### Task 2.1: Next.js 骨架

- `frontend/` 初始化
- `frontend/src/app/layout.tsx`
- `frontend/src/app/globals.css`（暗色主题）

#### Task 2.2: 布局组件

- AppShell, Sidebar, TopBar, PageHeader

#### Task 2.3: 首页

- `frontend/src/app/page.tsx`
- 主区域: Decision Center（DecisionCard 列表，level DESC + score DESC 排序）
- 顶部: AI Context Strip（当前语境 L2-L3）
- 右上角: Factory Index（小字）

#### Task 2.4: AI Context Strip 组件

- `frontend/src/components/ai/ContextStrip.tsx`
- 40px 高度，单行文本
- 角色感知（通过 API 传 role 参数）
- 点击操作链接执行 Action

---

### Phase 3: 业务中心

**目标:** 4 个业务中心页面，每个页面 = Context Strip + 子标签页 + 数据视图。

**Time:** 5 天

#### Task 3.1: 生产中心

- `frontend/src/app/production/page.tsx`
- 子标签: 今日总览 / 工单列表 / 效率看板 / 派工建议
- Context Strip 展示 L2-L3 生产相关洞察

#### Task 3.2: 设备中心

- `frontend/src/app/equipment/page.tsx`
- 子标签: 设备列表 / 工时分析 / 保养提醒

#### Task 3.3: 人员中心

- `frontend/src/app/personnel/page.tsx`
- 子标签: 在岗看板 / 效率排行 / 技能矩阵

#### Task 3.4: 物料中心

- `frontend/src/app/materials/page.tsx`
- 子标签: 缺料跟踪 / BOM展开 / 库存看板

---

### Phase 4: 数据中枢 + 设置

**Time:** 3 天

- 因果分析、来源追溯、本体视图
- 数据同步、收件箱管理
- 系统设置（7 个子标签页）

---

### Phase 5: AI 神经系统

**Time:** 3 天

- Priority Engine 深度集成（用真实事件训练分级 + 打分准确度）
- AI Context Strip 全页面生效 + 语境感知
- Cmd+K 全局命令面板（底层调用 IntentRouter + ReActAgent）
- Decision Center 自动填充 + 决策跟踪
- 所有业务中心的 AI 洞察接入

---

### Phase 6: 收尾

**Time:** 1 天

- 响应式适配
- 状态处理（加载、空、错误、边界）
- 部署

---

## 五、路由完整映射

```
/                          → 指挥中心（Decision Center）
/production                → 生产中心
/production?tab=today      → 今日总览
/production?tab=orders     → 工单列表
/production?tab=efficiency → 效率看板
/production?tab=dispatch   → 派工建议
/equipment                 → 设备中心
/equipment?tab=list        → 设备列表
/equipment?tab=analysis    → 工时分析
/equipment?tab=maintenance → 保养提醒
/personnel                 → 人员中心
/personnel?tab=dashboard   → 在岗看板
/personnel?tab=efficiency  → 效率排行
/personnel?tab=skills      → 技能矩阵
/personnel?tab=roster      → 在职清单
/materials                 → 物料中心
/materials?tab=shortages   → 缺料跟踪
/materials?tab=bom         → BOM展开
/materials?tab=stock       → 库存看板
/data                      → 数据中枢
/data?tab=causality        → 因果分析
/data?tab=tracing          → 来源追溯
/data?tab=ontology         → 本体视图
/data?tab=sync             → 数据同步
/data?tab=inbox            → 收件箱管理
/settings                  → 系统设置
/settings?tab=employees    → 员工管理
/settings?tab=erp          → ERP同步
/settings?tab=db           → 数据库配置
/settings?tab=llm          → LLM配置
/settings?tab=params       → 参数管理
```

**对比 Streamlit 现状：**

```
22 个独立文件          →  5 个路由 + searchParams 子视图
每个页面独立 CSS      →  全局 Design System 组件
AI 作为一个页面       →  AI 嵌入所有页面 + Decision Center
信息无差别推送        →  L1-L5 分级 + score 打分 + 语境过滤
```

---

## 六、删除清单

```bash
# Streamlit 页面（22 个文件）
rm app.py
rm pages/0_项目报工.py pages/1_组长报工.py pages/2_今日总览.py
rm pages/3_设备维度.py pages/4_人员维度.py pages/5_工单进度.py
rm pages/6_效率看板.py pages/7_标准工时健康度.py pages/8_缺料跟踪.py
rm pages/9_系统配置.py pages/10_BOM展开.py pages/11_人员看板.py
rm pages/12_因果分析.py pages/13_来源追溯.py pages/14_本体视图.py
rm pages/15_数据同步.py pages/16_智能助理.py pages/17_生产计划.py
rm pages/18_派工建议.py pages/20_收件箱管理.py pages/21_在职人员清单.py

# Streamlit 认证 + Copilot + 配置
rm core/auth.py
rm core/agent/copilot_widget.py
rm .streamlit/config.toml

# 旧设计文件
rm docs/design-preview*.html
```

---

## 七、关键设计决策记录

### 为什么 Phase 1 就做 Priority Engine

因为指挥中心（Phase 2）的内容完全依赖分级引擎的输出。没有 L1-L5 分级，首页要么是空的（没有数据），要么是旧的"仪表盘+决策卡片"拼凑。Priority Engine 是全系统的消息过滤器，越早做越早验证分级准确度。

### 为什么 AI Context Strip 只展示 L2-L3

- L1 不需要展示（纯记录）
- L2-L3 是"需要注意但不需要立即决策"，适合在浏览业务页面时作为上下文提示
- L4-L5 需要在 Decision Center 中正式处理，不适合挤在 40px 的细条里
- 这样 Context Strip 永远不会超过 1 行，永远不会变成"横幅广告"

### 为什么 Decision Center 放在首页主区域

- 打开系统的第一件事就是处理决策项
- Factory Index 放在右上角小字，纯粹作为参考，不占据注意力
- 没有待决策项时，可以空态展示"今天暂无待处理事项"

### 为什么不是 Storybook

Storybook 对于组件库项目是标准配置。但你的阶段（单人开发、无客户、核心逻辑已稳）——维护 Storybook 的性价比不如直接写组件然后通过业务页面验证。等第二个开发者加入时再上 Storybook 不迟。

### 为什么用 context_filter 而不是 role_filter

工厂里的"角色"不是静态标签。同一个人上午盯生产（关注工单延期），下午看物料（关注缺料），晚上处理客诉（关注交付）。单纯的 `role_filter()` 会让厂长永远看到 L4-L5 经营数据。`context_filter(role, current_page, current_focus)` 让 AI Context Strip 在每页只展示与该页相关的消息。**角色决定权限边界，语境决定展示内容。**

### 为什么事件模型要带 source + confidence

系统现有 4 个事件源头（ERP 同步、Excel 导入、Inbox AI、Agent 推理），可信度从 0.98 到 0.5 不等。没有 confidence 字段，AI 推理出的"可能延期"和 ERP 确认的"已延期"在系统中无法区分。现在加是加一个字段，未来补是重构整个管道。**更重要的是：低 confidence 事件不产生 L4-L5 决策，确保首页不会出现"AI 猜测"级别的消息。**

### 为什么同 level 内还需要 score

L3 风险跨度太大。"库存低于预警线"和"WO-1827 延期概率 80%"都可能是 L3，但前者 score=45（知道就行），后者 score=88（必须处理）。没有 score，50 个 L3 堆在 Decision Center 里，用户仍然不知道先处理哪个。**level 定类别，score 定顺序。**
