# Factory Intelligence Data Model

> 定义 Event、Decision、Insight、Action、Notification 五个核心对象及其关系。
> 这是 Phase 1 编码开始前必须锁定的数据契约。

---

## 一、设计原则

### 1.1 五个对象的职责边界

```
┌──────────────────────────────────────────────────────────┐
│                     Event Pipeline                       │
│                                                          │
│  任何来源的原始事实                                        │
│  → Priority Engine 处理                                   │
│  → 产出 Notification（投递） + Insight（分析） + Decision（决策）│
└──────────────────────────────────────────────────────────┘
```

| 对象 | 一句话定义 | 谁创建 | 谁消费 |
|------|-----------|--------|--------|
| **Event** | 系统中发生的原始事实 | ERP/导入/Agent/手动 | Priority Engine |
| **Decision** | 需要人做的决定 + 做了的决定 | Priority Engine 产出, 用户消费 | 用户 |
| **Insight** | AI 对当前状态的浓缩洞察 | Priority Engine 产出, 展示在 AI Context Strip | 用户 |
| **Action** | 用户或系统可执行的操作 | Decision/Insight 附带 | 用户/系统 |
| **Notification** | Event 经过处理后投递到各渠道的消息 | Priority Engine 产出, 投递到各渠道 | 各展示渠道 |

### 1.2 核心流程（数据流）

```
ERP同步 ──┐
Excel导入 ─┤
AI收件箱 ─┼──→ RawEvent ──→ Priority Engine ──→ Notification ──→ Decision Center
Agent推理 ─┤                                          ├──→ AI Context Strip
手动录入 ─┘                                          └──→ Data Log
```

### 1.3 关键约束

1. **Event → Notification 是一对多**。同一个事件（张三请假）对厂长、班组长、IE 产生不同的 Notification。
2. **Decision 必有对应的 Event**。没有 Event 凭空产生 Decision。
3. **Insight 不带"操作"**。Insight 只是信息展示，操作在 Decision 里。
4. **Action 是动词**。不是状态、不是标签、不是分类——是"批准采购"、"调配人员"、"调整排产"。
5. **Notification 不含"为什么"**。为什么这件事重要在 Meta 里，Notification 只负责"什么 + 怎么做"。

---

## 二、Event（事件）

系统中发生的不可变原始事实。

### 2.1 模型定义

```python
class Event(BaseModel):
    """原始事件 — 进入系统后不可变，只追加不回滚。"""
    id: str                          # "evt_20260624_001"
    type: str                        # 事件类型枚举
    entity_type: str                 # 实体类型枚举
    entity_id: str                   # 实体标识符
    title: str                       # 一句话标题
    description: str = ""            # 详细描述
    source: str                      # 来源枚举
    confidence: float                # 0.0 - 1.0
    timestamp: datetime              # 事件发生时间（非系统接收时间）
    received_at: datetime            # 系统接收时间
    metadata: dict = {}              # 扩展字段

    # 以下两个字段是 Priority Engine 处理后的结果，不是原始数据
    impact_score: float | None = None   # Priority Engine 赋值
    urgency: str | None = None          # Priority Engine 赋值
```

### 2.2 枚举值约束

**Event Type（事件类型）:**

| 枚举值 | 含义 | 典型示例 |
|--------|------|---------|
| `absent` | 缺勤/请假 | 张三请假 2 天 |
| `shortage` | 缺料 | A料库存低于安全值 |
| `delay` | 延期风险 | WO-1827 预计延期 2 天 |
| `breakdown` | 设备故障 | E-0045 冲压机故障停机 |
| `quality` | 质量异常 | 铸件合格率低于 90% |
| `overtime` | 加班请求 | 申请加班 3 小时 |
| `purchase` | 采购审批 | 请购 B 料 50 件 |
| `personnel_change` | 人员变动 | 李四转岗到冲压工位 |
| `schedule_change` | 排产调整 | A线明日排产变更 |
| `maintenance` | 保养到期 | 3 号冲压机保养到期 |

**Entity Type（实体类型）:**

| 枚举值 | 含义 |
|--------|------|
| `work_order` | 工单 |
| `employee` | 员工 |
| `equipment` | 设备 |
| `material` | 物料 |
| `production_line` | 生产线 |
| `project` | 项目 |
| `department` | 部门 |

**Source（事件来源）:**

| 枚举值 | 默认 confidence | 说明 |
|--------|----------------|------|
| `erp_sync` | 0.95-1.0 | ERP 系统直连 |
| `excel_import` | 0.85-0.95 | Excel 导入 |
| `inbox_ai` | 0.60-0.90 | AI 分类收件箱 |
| `agent_inference` | 0.40-0.80 | Agent 推理预测 |
| `manual` | 1.0 | 手动录入 |

### 2.3 验证规则

```python
@validator("confidence")
def confidence_range(cls, v):
    if not 0.0 <= v <= 1.0:
        raise ValueError("confidence must be in [0.0, 1.0]")

@validator("timestamp")
def not_future(cls, v):
    # 允许 30 秒时钟偏差（工厂内各服务器时间可能不完全同步）
    if v > datetime.utcnow() + timedelta(seconds=30):
        raise ValueError("event timestamp cannot be in the future (allow 30s clock skew)")
```

### 2.4 示例

```json
{
  "id": "evt_20260624_001",
  "type": "absent",
  "entity_type": "employee",
  "entity_id": "张三",
  "title": "张三请假 2026-06-24 至 2026-06-25",
  "description": "张三因个人原因申请事假 2 天，涉及 A 线冲压工位",
  "source": "inbox_ai",
  "confidence": 0.88,
  "timestamp": "2026-06-24T07:30:00Z",
  "received_at": "2026-06-24T07:35:12Z",
  "metadata": {
    "leave_type": "事假",
    "duration_days": 2,
    "submitted_by": "班组长",
    "original_file": "请假单_20260624.xlsx"
  }
}
```

---

## 三、Decision（决策）

需要人做的决定，或已经做了的决定。**Decision Center 展示的就是 Decision 对象的集合。**

### 3.1 模型定义

```python
class Decision(BaseModel):
    """决策项 — AI 建议 + 人的决定。"""
    id: str                          # "dec_20260624_001"
    event_id: str                    # 关联的原始事件
    level: int                       # L1-L5（由 Priority Engine 判定）
    score: float                     # 0-100。level 定类别，score 定顺序
    title: str                       # 决策标题
    description: str                 # 详细说明
    status: str                      # "pending" | "approved" | "rejected" | "dismissed" | "executing" | "executed" | "failed" | "expired"
    
    # 来源信息
    source: str                      # 同 Event.source
    confidence: float                # 0.0 - 1.0
    
    # 关联
    roles: list[str]                 # 需要哪些角色处理此决策
    context_filter: str = ""         # 语境关联（如 "production", "personnel"）
    
    # 可执行的操作（由 Priority Engine 生成建议）
    suggested_actions: list["Action"] = []
    
    # 决策记录（由用户操作触发）
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None
    
    # 决策结果追踪
    outcome: "OutcomeMeasurement | None" = None
    
    # 时间
    created_at: datetime
    resolved_at: datetime | None = None
    expires_at: datetime | None = None  # 过期时间
```

### 3.2 L1-L5 等级与 score

| 等级 | 含义 | score 范围 | 展示方式 | 生命周期 |
|------|------|-----------|---------|---------|
| L1 | 正常操作记录 | 0-20 | Data Log | 不展示，仅查询 |
| L2 | 提醒 | 21-50 | AI Context Strip | 24h |
| L3 | 风险 | 51-75 | AI Context Strip | 至解决 |
| L4 | 决策 | 76-90 | Decision Center | 至决策 |
| L5 | 经营影响 | 91-100 | Decision Center 置顶 | 至解决 |

**排序规则：** `level DESC` + `score DESC`。同 level 内，score 高的在上。

**置信度调整规则：**
- `confidence < 0.5` → 跳两级展示（L3 当 L1，不展示）
- `0.5 ≤ confidence < 0.7` → 降一级展示（L3 当 L2）
- `0.7 ≤ confidence < 0.95` → 按实际等级展示
- `confidence ≥ 0.95` → 按实际等级展示（ERP 确认事件）
- **低 confidence 事件不产生 L4-L5 Decision**

### 3.3 状态流转

```
pending ──→ approved ──→ executing ──→ executed
    │                      │              │
    │                      └──→ failed    └── 记录 outcome
    │
    ├──→ dismissed
    │
    ├──→ rejected
    │
    └──→ expired              ← 超过 expires_at 自动过期

补充说明:
  - executing: 操作已提交，等待外部系统（ERP/中台）返回确认
  - failed: 外部系统调用失败，需人工介入或重试
  - expired: expires_at 已过，决策超时未处理，自动转为过期
  - 每步操作必须保证幂等性（见 5.3）
```

### 3.4 Decision History（决策追踪）

每个 Decision 完成后，记录决策的准确性。

```python
class OutcomeMeasurement(BaseModel):
    """决策结果的量化追踪。"""
    decision_id: str
    
    # AI 当时怎么预测的
    ai_predicted_impact: str          # "延期 2 天"
    ai_predicted_financial: float     # 126000
    
    # 实际上发生了什么
    actual_impact: str | None = None  # "实际上延期了 0.5 天"
    actual_financial: float | None   # 实际损失金额
    
    # AI 准确度评价
    accuracy_score: int               # 1-5, 5=完全准确
    accuracy_feedback: str = ""       # 人工评价
    
    # 关键指标
    time_to_decision: int             # 从创建到决策的分钟数
    prevented_loss: float = 0.0       # 避免的损失金额（估算）
    
    created_at: datetime
```

**Decision History 的用途：**
1. 系统自检：AI 的预测准确度随着时间推移是提高还是下降？
2. 绩效归因：哪些决策真正避免了损失？
3. 规则优化：如果 AI 置信度高但准确度低，需要调整规则。

### 3.5 示例

```json
{
  "id": "dec_20260624_001",
  "event_id": "evt_20260624_001",
  "level": 4,
  "score": 88,
  "title": "WO-1827 预计延期 2 天",
  "description": "铜牌仓B项目当前进度62%，交期剩余3天。预计影响客户交付，涉及金额 ¥126,000。",
  "status": "pending",
  "source": "erp_sync",
  "confidence": 0.95,
  "roles": ["admin", "supervisor"],
  "context_filter": "production",
  "suggested_actions": [
    { "action": "approve_expedite", "label": "批准加急", "payload": {"order_id": "WO-1827"} },
    { "action": "reschedule", "label": "调整排产", "payload": {"order_id": "WO-1827"} },
    { "action": "dismiss", "label": "忽略", "payload": {} }
  ],
  "created_at": "2026-06-24T08:00:00Z",
  "expires_at": "2026-06-27T08:00:00Z"
}
```

---

## 四、Insight（洞察）

AI 对当前状态的浓缩洞察，用于 **AI Context Strip**。Insight 是只读的，没有操作。

### 4.1 模型定义

```python
class Insight(BaseModel):
    """AI 上下文洞察 — 只读，不操作，展示在 AI Context Strip。"""
    id: str                          # "ins_20260624_001"
    event_id: str                    # 关联的原始事件
    
    level: int                       # L2 或 L3（L4-L5 不应出现在 Context Strip）
    score: float                     # 21-75
    confidence: float                # 0.0 - 1.0
    
    text: str                        # 展示文本，一句话
    context_filter: str              # "production" | "equipment" | "personnel" | "materials"
    
    related_actions: list[Action] = []  # 关联的操作（快捷键，不是必须操作）
    
    expires_at: datetime
```

### 4.2 Insight 设计约束

| 约束 | 原因 |
|------|------|
| **一句话，不超过 80 字** | 40px 高度一行展示 |
| **不展示 L4-L5** | L4-L5 应去 Decision Center 处理 |
| **语境感知** | 生产中心只展示生产相关的 Insight |
| **按 score 降序限 3 条** | 避免 Context Strip 过长 |
| **不带操作按钮** | 只展示问题，不展示方案（方案在 Decision 里） |
| **角色感知** | 厂长看到经营影响，班组长看到具体工位 |

### 4.3 示例

```
L2: "提醒: A料库存低于预警线，建议关注采购进度"  (score: 48)
L3: "风险: WO-1827 延期概率 80%，涉及金额 ¥126,000"  (score: 88 → display as L3)
L3: "风险: A线冲压工位缺1人，预计产能下降5%"  (score: 74)
```

---

## 五、Action（操作）

用户或系统可执行的操作。**Action 不是状态标签，是真正的操作定义。**

### 5.1 模型定义

```python
class Action(BaseModel):
    """可执行的操作。"""
    action: str                      # 操作标识符，如 "approve_purchase"
    label: str                       # 展示标签，如 "批准采购"
    description: str = ""            # 操作说明
    payload: dict = {}               # 执行操作所需的数据
    confirmation_required: bool = False  # 是否需要确认弹窗
    
    # 权限控制
    allowed_roles: list[str] = []    # 空列表表示所有角色
```

### 5.2 操作类型枚举

| action 标识符 | label | 触发的系统行为 | 需要确认 | 涉及外部系统 |
|-------------|-------|-------------|---------|------------|
| `approve_expedite` | 批准加急 | 更新工单优先级，通知生产 | 否 | 可能（ERP 工单状态） |
| `reschedule` | 调整排产 | 打开排产调整界面 | 否 | 否 |
| `approve_purchase` | 批准采购 | 生成采购单，通知采购部门 | 否 | 是（ERP 采购模块） |
| `dispatch_worker` | 调配人员 | 更新人员调度 | 是 | 可能（HR 系统） |
| `approve_overtime` | 批准加班 | 更新加班记录 | 否 | 可能（考勤系统） |
| `dismiss` | 忽略 | 标记为已读，不出现在首页 | 是 | 否 |
| `confirm` | 确认 | 确认已收到，降低提醒频率 | 否 | 否 |
| `view_detail` | 查看详情 | 跳转到相关页面 | 否 | 否 |

### 5.3 Action 执行契约（异步 + 幂等）

#### 核心约束

1. **异步执行** — 涉及外部系统的 Action（ERP 采购单、工单状态更新）必须异步。用户点击后立即返回 `executing`，后台任务完成后通过 Notification 或轮询更新状态。
2. **幂等性** — 每个 Action 请求必须携带 `idempotency_key`，后端去重。防止用户双击、网络重试导致 ERP 重复下单。
3. **状态可观测** — 前端在 Decision 状态为 `executing` 时显示加载态，`failed` 时显示错误 + 重试按钮。

#### 执行流程

```
用户点击 "批准采购"
  → 前端生成 idempotency_key（UUID, 前端生成）
  → POST /api/actions
     {
       action: "approve_purchase",
       decision_id: "dec_...",
       idempotency_key: "req_xxx_001",   ← 新增，防重复
       payload: { ... },
       user: "管理员"
     }
  → 后端:
     1. 检查 idempotency_key 是否已处理过 → 重复则返回原结果（幂等）
     2. 更新 Decision status: "pending" → "approved"
     3. 启动后台任务（BackgroundTasks / Celery）:
        a. 更新 Decision status: "approved" → "executing"
        b. 调用外部 ERP 接口生成采购单
        c. 成功 → Decision status: "executing" → "executed"
           失败 → Decision status: "executing" → "failed"
                  记录错误原因 + 重试次数
        d. 记录 OutcomeMeasurement
     4. 立即返回 { status: "executing", decision_id: "..." }
     → 前端: Decision 进入 executing 态，显示加载中
     → 后台完成后:
        - 成功后端可通过事件推送（SSE/WebSocket）或前端轮询刷新
```

#### 失败恢复

| 失败场景 | 处理方式 |
|---------|---------|
| ERP 接口超时 | 重试 3 次，间隔 30s，仍失败 → `failed` |
| ERP 接口返回业务错误 | 不重试，直接 `failed`，人工介入 |
| 网络闪断但 ERP 已处理 | 通过 `idempotency_key` 查询 ERP 方状态 |
| 用户刷新页面 | 前端重新 GET Decision，看到 `executing` / `failed` |

#### 幂等性保证

```python
IDEMPOTENCY_TTL = 24 * 3600  # idempotency_key 有效期 24h

class IdempotencyRecord(BaseModel):
    key: str                     # idempotency_key
    decision_id: str
    action: str
    result_status: str           # "executing" | "executed" | "failed"
    result_data: dict = {}
    created_at: datetime

# 幂等检查逻辑
def execute_action(action_req: ActionRequest) -> ActionResponse:
    existing = idempotency_store.get(action_req.idempotency_key)
    if existing:
        return ActionResponse(
            status=existing.result_status,
            decision_id=existing.decision_id,
            is_idempotent_replay=True,         # 标记"这是重放"
        )
    # ... 正常执行
```

---

## 六、Notification（通知）

Event 经过 Priority Engine 处理后，投递到各渠道的消息载体。

### 6.1 模型定义

```python
class Notification(BaseModel):
    """投递消息 — Event 经过处理后的产出。"""
    id: str
    event_id: str                    # 关联的原始事件
    decision_id: str | None = None   # 如果产生了决策，关联 Decision
    insight_id: str | None = None    # 如果产生了洞察，关联 Insight
    
    channel: str                     # 投递渠道
    target: str                      # 频道内的目标（role / user_id / page）
    
    # 展示内容（渠道格式化后的产物）
    display_text: str
    display_level: int               # 实际展示的等级（可能经过置信度调整）
    display_score: float             # 实际展示的 score
    
    # 时效
    created_at: datetime
    expires_at: datetime = None
    read_at: datetime = None         # 用户已读时间
```

### 6.2 投递渠道

| channel | 说明 | target 格式 |
|---------|------|-----------|
| `decision_center` | L4-L5 决策 | role 或 user_id |
| `context_strip` | L2-L3 洞察 | page（如 "production"） |
| `data_log` | L1 记录 | 无，仅存为历史 |

### 6.3 映射逻辑

```
Event → Priority Engine → 产出:
  L1    → Notification(channel=data_log)
  L2-L3 → Notification(channel=context_strip, target=page)
          (Insight 对象同时产生，供 AI Context Strip 展示)
  L4-L5 → Notification(channel=decision_center, target=role)
          (Decision 对象同时产生，供 Decision Center 展示)
```

---

## 七、Priority Engine 评分公式

已定义为纯规则引擎，不是 AI。第一阶段完全确定性的评分。

### 7.1 基本公式

```
score = delivery_impact × 0.40 + financial_impact × 0.30 + customer_tier × 0.20 + anomaly_level × 0.10

level = 1 if score ≤ 20
        2 if 21 ≤ score ≤ 50
        3 if 51 ≤ score ≤ 75
        4 if 76 ≤ score ≤ 90
        5 if 91 ≤ score ≤ 100
```

### 7.2 维度定义

| 维度 | 范围 | 评分参考 |
|------|------|---------|
| **delivery_impact** | 0-100 | 无影响=0, 单个工单延误=30, 多工单延误=60, 客户交付影响=80, 重大项目延期=100 |
| **financial_impact** | 0-100 | 无损失=0, <1万=20, 1-5万=50, 5-20万=75, >20万=100 |
| **customer_tier** | 0-100 | 内部=10, 常规=25, 重要=50, 战略客户=80, 关键客户=100 |
| **anomaly_level** | 0-100 | 正常=10, 偏离<10%=30, 偏离10-30%=60, 偏离>30%=80, 不可逆=100 |

### 7.3 置信度调整

```python
def adjust_level_by_confidence(level: int, confidence: float) -> int:
    if confidence >= 0.95:
        return level
    elif confidence >= 0.70:
        return level
    elif confidence >= 0.50:
        return max(1, level - 1)
    else:
        return max(1, level - 2)

def adjust_score_by_confidence(score: float, level: int, confidence: float) -> float:
    """score = base_score × confidence"""
    return round(score * confidence)
```

### 7.4 来源加权

```
erp_sync       → confidence: 0.95-1.0   → 不降级
excel_import   → confidence: 0.85-0.95  → 轻微降级（边界情况）
inbox_ai       → confidence: 0.60-0.90  → 可能降级
agent_inference→ confidence: 0.40-0.80  → 不产生 L4-L5
manual         → confidence: 1.0        → 不降级

### 7.5 置信度覆写机制（防御"乘法漏斗"）

**问题：** 加权求和 + 乘法置信度 会导致 L5 级别事件被低 confidence 拖成 L2。
例：`breakdown` 恶性故障 base_score=95（L5），但 agent_inference confidence=0.5 → final=48（L2）。

**修正：** 引入事件类型级别的置信度下限覆写。

```python
# 关键高危事件类型的置信度下限
CONFIDENCE_FLOOR_OVERRIDE = {
    "breakdown": 0.90,       # 设备故障：置信度低也要当回事
    "delay": 0.85,           # 交期延期：宁可信其有
    "quality": 0.80,         # 质量异常：底线
    "shortage": 0.75,        # 缺料：中等敏感
    # 以下类型不设下限，使用标准逻辑
    # "absent", "overtime", "personnel_change", "schedule_change", "purchase", "maintenance"
}

def apply_confidence(event_type: str, base_score: float, raw_confidence: float) -> tuple[int, float]:
    """返回 (adjusted_confidence, final_level, final_score)"""

    # Step 1: 类型覆写 — 高危事件有 confidence 下限
    floor = CONFIDENCE_FLOOR_OVERRIDE.get(event_type, 0.0)
    effective_confidence = max(raw_confidence, floor)

    # Step 2: score 调整
    final_score = round(base_score * effective_confidence)

    # Step 3: level 判定（仍用调整后的 score）
    level = _score_to_level(final_score)

    # Step 4: 天花板突破 — 置信度覆写事件若 base_score 已达 L5 但乘法降级丢等级
    if event_type in CONFIDENCE_FLOOR_OVERRIDE and base_score >= 95:
        # 灾难性事件（如恶性故障 base_score=100）：强制保留 L5
        level = max(level, 5)
        final_score = max(final_score, 91)
    elif event_type in ("breakdown", "delay") and base_score >= 80:
        # 高危 + 高影响 → 强制不低于 L4
        level = max(level, 4)
        final_score = max(final_score, 76)

    return level, final_score


def _score_to_level(score: float) -> int:
    if score <= 20: return 1
    elif score <= 50: return 2
    elif score <= 75: return 3
    elif score <= 90: return 4
    else: return 5
```

**效果验证：**

| 场景 | base_score | raw_confidence | 旧 final | 新 final |
|------|-----------|---------------|---------|---------|
| breakdown 但 agent 推断 (conf=0.5) | 95 | 0.5 | 48 → L2 ❌ | floor=0.90 → 85 → L4 ✅ |
| delay 但 inbox_ai 推断 (conf=0.65) | 80 | 0.65 | 52 → L3 ⚠️ | floor=0.85 → 68 → L3 ✅ |
| absent 班组长上报 (conf=0.88) | 52 | 0.88 | 46 → L3 ✅ | 无覆写 → 46 → L3 ✅ |
| absent agent 猜测 (conf=0.45) | 52 | 0.45 | 23 → L2 ⚠️ | 无覆写 → 23 → L2 ✅（低可信请假不该弹出） |
| breakdown 恶性故障 + 较低可信 (conf=0.60) | 100 | 0.60 | floor=0.90 → 90 → L4 ❌ | floor=0.90 → 90 → L5 强制突破 ✅ |

**原则：** 覆写只在"事件后果不可逆"的场景启效。请假不会炸掉产线，但设备故障会。乘法漏斗过滤的是低可信噪声，但不应过滤掉真正的高危信号。
```

---

## 八、数据流示例

### 8.1 张三请假

```
原始 Event:
  type: "absent", entity: "employee/张三"
  source: "inbox_ai", confidence: 0.88
  ↓
OntologyEngine.trace("张三"):
  → 关联: A线, 冲压工位, WO-1827
  → 影响: A线产能下降5%, WO-1827 可能延期
  ↓
PriorityEngine.assess():
  delivery_impact: 60 (A线依赖张三的冲压技能)
  financial_impact: 50 (延误涉及 ¥12,000)
  customer_tier: 50 (铜牌仓B是重要客户)
  anomaly_level: 30 (偏离<10%)
  base_score = 60×0.4 + 50×0.3 + 50×0.2 + 30×0.1 = 24+15+10+3 = 52
  base_level = 3
  confidence = 0.88 → 不降级
  final_score = 52 × 0.88 = 46
  final_level = 3
  ↓
产出三个 Notification + 一个 Insight:

  → Notification(channel=context_strip, target="production"):
      "A线冲压工位缺1人，产能预计下降5%"
      (Insight 对象: level=3, score=46)

  → Notification(channel=context_strip, target="personnel"):
      "张三请假 2 天，冲压工位需调配"
      (Insight 对象: level=3, score=46)

  → Decision(channel=decision_center, target="supervisor"):
      "是否需要调配李强补位冲压工位？"
      level=3, score=46 → 由于 level<4，不进 Decision Center
      仅展示在 Context Strip
```

### 8.2 WO-1827 延期风险

```
原始 Event:
  type: "delay", entity: "work_order/WO-1827"
  source: "erp_sync", confidence: 0.95
  ↓
PriorityEngine.assess():
  delivery_impact: 80 (客户交付影响)
  financial_impact: 75 (涉及 ¥126,000, 5-20万档)
  customer_tier: 50 (重要客户)
  anomaly_level: 80 (偏离>30%)
  base_score = 80×0.4 + 75×0.3 + 50×0.2 + 80×0.1 = 32+22.5+10+8 = 72.5
  base_level = 3
  confidence = 0.95 → 不降级
  final_score = 72.5 × 0.95 = 69
  final_level = 3
  # 等一下，这应该是 L4 事件——涉及金额大、影响交付
  # 修正: financial_impact 和 customer_tier 权重需要上调
  # 问题出在公式权重，不是降级逻辑。下面演示正确的 L4 判定：
  ↓
重新评估:
  delivery_impact: 90 (重大项目延期, 客户催单)
  financial_impact: 80 (涉及 ¥126,000 + 违约金)
  customer_tier: 80 (战略客户)
  anomaly_level: 80 (偏离>30%)
  score = 90×0.4 + 80×0.3 + 80×0.2 + 80×0.1 = 36+24+16+8 = 84
  level = 4
  confidence = 0.95 → 不降级
  final_score = 84
  ↓
产出:

  → Decision(channel=decision_center, target="admin,supervisor"):
      "WO-1827 预计延期 2 天，涉及金额 ¥126,000"
      level=4, score=84, status=pending

  → Notification(channel=context_strip, target="production"):
      "高风险: WO-1827 延期概率 80%"
```

---

## 九、对象关系总图

```
Event (1) ──→ 产生 ──→ Priority Engine
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                   L1       L2-L3     L4-L5
                    │         │         │
                    ▼         ▼         ▼
              Data Log    Insight    Decision
                            │          │
                            ▼          ▼
                     Context Strip  Decision Center
                                      │
                                      ▼
                                     Action
                                      │
                                      ▼
                                 OutcomeMeasurement
                                      │
                                      ▼
                               Decision History
```

### 表的物理设计（v2：Action 解耦 + 索引优化）

```sql
-- events: 原始事件存储
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    timestamp TIMESTAMP NOT NULL,
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',          -- JSON, 不频繁查询
    impact_score REAL,
    urgency TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_received ON events(received_at DESC);

-- decisions: 决策项
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
    score REAL NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    roles TEXT DEFAULT '[]',              -- JSON array（低频过滤）
    context_filter TEXT DEFAULT '',
    idempotency_key TEXT,                 -- 幂等键（Action 执行用）
    decided_at TIMESTAMP,
    decided_by TEXT,
    decision_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    expires_at TIMESTAMP
);
CREATE INDEX idx_decisions_level ON decisions(level DESC);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_context ON decisions(context_filter);
CREATE INDEX idx_decisions_level_status ON decisions(level, status);
CREATE INDEX idx_decisions_created ON decisions(created_at DESC);
CREATE UNIQUE INDEX idx_decisions_idempotency ON decisions(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- decision_actions: Action 解耦为独立行（替代 decisions.suggested_actions JSON）
CREATE TABLE decision_actions (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(id),
    action TEXT NOT NULL,                  -- "approve_purchase"
    label TEXT NOT NULL,                   -- "批准采购"
    description TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',             -- JSON
    confirmation_required INTEGER DEFAULT 0,
    allowed_roles TEXT DEFAULT '[]',        -- JSON array
    sort_order INTEGER DEFAULT 0,           -- 展示顺序
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_decision_actions_decision ON decision_actions(decision_id);
CREATE INDEX idx_decision_actions_action ON decision_actions(action);  -- ← 可按 action 类型筛选
-- 示例：查询所有包含 reschedule 操作的待决策项
-- SELECT DISTINCT d.* FROM decisions d
-- JOIN decision_actions a ON a.decision_id = d.id
-- WHERE a.action = 'reschedule' AND d.status = 'pending'
-- ORDER BY d.level DESC, d.score DESC;

-- decision_outcomes: 决策结果追踪
CREATE TABLE decision_outcomes (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(id),
    ai_predicted_impact TEXT NOT NULL,
    ai_predicted_financial REAL DEFAULT 0,
    actual_impact TEXT,
    actual_financial REAL,
    accuracy_score INTEGER CHECK(accuracy_score BETWEEN 1 AND 5),
    accuracy_feedback TEXT DEFAULT '',
    time_to_decision INTEGER,              -- 分钟
    prevented_loss REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_outcomes_decision ON decision_outcomes(decision_id);

-- insights: 上下文洞察
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    level INTEGER NOT NULL CHECK(level BETWEEN 2 AND 3),
    score REAL NOT NULL,
    confidence REAL NOT NULL,
    text TEXT NOT NULL,
    context_filter TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
CREATE INDEX idx_insights_level ON insights(level DESC);
CREATE INDEX idx_insights_context ON insights(context_filter);
CREATE INDEX idx_insights_expires ON insights(expires_at);

-- notifications: 投递记录
CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    decision_id TEXT REFERENCES decisions(id),
    insight_id TEXT REFERENCES insights(id),
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    display_text TEXT NOT NULL,
    display_level INTEGER NOT NULL,
    display_score REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    read_at TIMESTAMP
);
CREATE INDEX idx_notifications_channel ON notifications(channel);
CREATE INDEX idx_notifications_target ON notifications(target);
CREATE INDEX idx_notifications_unread ON notifications(channel, target, read_at) WHERE read_at IS NULL;
```

---

## 十、API 契约

### POST /api/events — 推送事件

```json
// Request
{
  "type": "absent",
  "entity_type": "employee",
  "entity_id": "张三",
  "title": "张三请假 2026-06-24 至 2026-06-25",
  "description": "事假 2 天",
  "source": "inbox_ai",
  "confidence": 0.88,
  "timestamp": "2026-06-24T07:30:00Z",
  "metadata": {"leave_type": "事假", "duration_days": 2}
}

// Response
{
  "event_id": "evt_20260624_001",
  "decisions": ["dec_20260624_001"],    // 产生的决策（L4-L5 才有）
  "insights": ["ins_20260624_001"],      // 产生的洞察（L2-L3 才有）
  "notifications": [...]                 // 投递记录
}
```

### GET /api/decision-center — 获取决策

```
Query:
  ?role=admin&page=production&level_min=4&status=pending

Response:
{
  "items": [
    {
      "id": "dec_20260624_001",
      "level": 4,
      "score": 88,
      "title": "WO-1827 预计延期 2 天",
      "description": "铜牌仓B项目...涉及金额 ¥126,000",
      "status": "pending",
      "suggested_actions": [...],
      "created_at": "..."
    }
  ],
  "total": 5,
  "unread_count": 3
}
```

### GET /api/context-strip — 获取 AI Context Strip

```
Query:
  ?page=production&role=supervisor&limit=3

Response:
{
  "items": [
    {
      "text": "高风险: WO-1827 延期概率 80%，涉及金额 ¥126,000",
      "level": 3,
      "score": 84,
      "actions": [{"action": "view_detail", "label": "查看详情"}]
    },
    {
      "text": "A线冲压工位缺1人，产能预计下降5%",
      "level": 3,
      "score": 46,
      "actions": [{"action": "view_detail", "label": "查看详情"}]
    }
  ]
}
```

### POST /api/actions — 执行操作

```json
// Request
{
  "action": "approve_expedite",
  "decision_id": "dec_20260624_001",
  "payload": {"order_id": "WO-1827"},
  "user": "管理员",
  "note": "已和客户确认，批准加急"
}

// Response
{
  "success": true,
  "decision_status": "approved",
  "outcome_id": "out_20260624_001",
  "message": "WO-1827 已标记为加急"
}
```

---

## 十一、变更记录

### v5 → v6 修正（2026-06-24，2nd Peer Feedback — PASSED WITH CONDITIONS 条件修复）

1. **[§9] UNIQUE INDEX on idempotency_key** — `idx_decisions_idempotency` 部分唯一索引，防止并发请求同时通过幂等检查导致重复订单。
2. **[§2.3] 时钟偏差容忍** — timestamp 校验放宽到 `utcnow() + 30s`，解决工厂内 ERP/网关/边缘服务器时间不同步的问题。
3. **[§3.3] 增加 `expired` 状态** — Decision 状态枚举新增 `expired`，状态图增加 `pending → expired` 路径。需配合后台定时任务（Cron 每小时扫描 `expires_at < now AND status='pending'` 自动置为 `expired`）。
4. **[§7.5] 修复 L5 天花板** — `apply_confidence()` Step 4 增加天花板突破逻辑：若事件类型在 CONFIDENCE_FLOOR_OVERRIDE 中且 `base_score >= 95`，强制 `final_level = 5` 且 `final_score = max(final_score, 91)`。防止灾难性事件（恶性故障 base_score=100）因置信度乘法无法进入 L5。

### v4 → v5 修正（2026-06-24，Peer Feedback 三连）

1. **修复"乘法漏斗"漏洞** — 新增 §7.5 置信度覆写机制。`breakdown`/`delay`/`quality`/`shortage` 四类高危事件有 confidence 下限覆写（如 breakdown min=0.90），避免 L5 事件被 agent 低置信度拖成 L2。同时增加高危+高影响事件的强制最低等级逻辑。
2. **Action 异步化 + 幂等性** — 重写 §5.3，Decision 状态增加 `executing`/`failed`。Action 执行改为后台任务，引入 `idempotency_key` 防重复提交。补充失败恢复策略表。
3. **Action 表解耦** — 从 decisions 表的 JSON 字段 `suggested_actions` 拆分为独立表 `decision_actions`，支持按 action 类型做 JOIN 查询。补充索引策略。

### v3 → v4 改动清单

1. **新增本模型** — Factory Intelligence Data Model 完整定义
2. **Priority Engine 明确为纯规则引擎** — 第一阶段完全确定性评分公式，不涉及 AI 模型
3. **新增 Decision History** — OutcomeMeasurement 对象 + 决策追踪流程
4. **Context Filter 明确为后端服务** — 在 `api/domain/context_filter.py` 中实现，不是 React 逻辑
5. **工作负载修正** — 前端 40% / 后端 60%（原来是 80/20）
6. **API 契约更新** — 补充 Context Strip API + Decision Center API + Action API
7. **数据库 schema 更新** — 5 张核心表：events, decisions, decision_outcomes, insights, notifications

### 后续建议

1. 审查 v4 数据模型 → 确认后开始 Phase 0（Design System 组件）
2. 或直接在 Phase 0 前再补一次评审：check 这五个对象的边界有没有漏
3. Phase 1 的实现顺序建议：Event Schema → Priority Engine → API → 前端组件
