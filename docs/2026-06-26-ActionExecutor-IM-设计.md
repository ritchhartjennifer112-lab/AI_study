# ActionExecutor + IM 集成 — 方案设计

> 日期：2026-06-26 | 版本：v2.0 | 状态：待审批
>
> **v2.0 变更：** 补充 Sagas 补偿模式 / Row Guard 分页 / SQL 安全沙箱 / IM 流式状态卡片 / 置信度→数据质量联动 / 定时任务幂等约束

---

## 一、问题定义

### 1.1 当前系统的三处断点

| 断点 | 现象 | 根因 |
|------|------|------|
| **Agent 不能写** | ReAct Agent 的 40+ 工具全是只读，无法创建/修改记录 | `generic_tools.py` 硬编码拒绝非 SELECT SQL；core/ 的写函数未注册为 Agent 工具 |
| **ERP 同步不能触发** | `erp_sync.py` 已实现完整同步逻辑，但 Agent 不知道它的存在 | 同步函数未注册到 ToolRegistry |
| **审批后不执行** | `decision_service.execute_action()` 只改了 `status` 字段，没有执行任何实际操作 | 缺少 ActionExecutor 层把 Decision 映射到真实操作 |

### 1.2 设计目标

1. 补齐 **Event → Decision → Action → 执行** 闭环
2. 将 Agent 工具从 **40+ 语义工具** 重构为 **5-8 个基础原语**，由 LLM 自主组合
3. 引入 **三级风险分级** 控制 Agent 自主权
4. 接入 **钉钉** 作为 IM 通道（消息入口 + 审批反馈）
5. **生产级防御**：SQL 安全沙箱、Row Guard 分页、Sagas 补偿回滚、定时任务幂等、置信度→数据质量联动

---

## 二、核心理念：工具原语替代语义工具

### 2.1 当前模式的问题

当前 ToolRegistry 注册了 40+ 语义工具（"查询设备维度""查询人员维度""查询工单进度"…），每个工具只能做一件预定义的事。这导致的后果：

- **新增分析需求 = 必须写新工具**。用户问"哪台设备最近三天效率最低"，如果没有预定义的"查询设备效率趋势"工具，Agent 就回答不了
- **工具间不能组合**。LLM 自己推理说"这个问题需要先查工单进度，再查缺料，再交叉分析"，但两个语义工具返回的是不同结构的 HTML 数据，LLM 无法拼起来
- **维护负担线性增长**。业务需求每增加一种，工具文件就多一个函数

### 2.2 新设计：极简原语 + LLM 组合

参考 Claude Code 的设计哲学——**6 个基础工具覆盖所有操作**：

```
Claude Code:              工厂系统对标:
─────────────────────     ──────────────────────
Read(读取文件)      →     查询数据库 (SELECT SQL) + 读取文件 (Excel/CSV/图片)
Write(写入文件)     →     执行写操作 (参数化写入，非裸SQL)
Edit(编辑文件)      →     更新记录 (参数化UPDATE)
Bash(运行命令)      →     调用API (ERP同步/外部接口) + 调度任务 (定时/异步)
Glob(文件搜索)      →     搜索数据 (按实体/字段/关键词搜索)
Grep(内容搜索)      →     统计数据 (分组/排序/聚合/透视)
```

### 2.3 原语列表

| # | 原语名称 | 功能 | 对标 CC | 风险等级 |
|---|---------|------|---------|---------|
| 1 | `query_data` | 执行只读 SQL（SELECT/WITH），内置 Row Guard + SQL 沙箱，详见 [§2.5](#25-sql-) | Read | L0 |
| 2 | `search_entities` | 按类型+关键词搜索实体（员工/工单/设备/物料） | Glob+Grep | L0 |
| 3 | `read_file` | 读取 Excel/CSV/PDF/图片，返回结构化数据 | Read | L0 |
| 4 | `aggregate_data` | 分组统计/排序/透视/汇总（封装 group+sort+summarize） | Grep | L0 |
| 5 | `execute_write` | 参数化写入操作（INSERT/UPDATE/DELETE），不接受裸SQL。每条写操作必须附带 `reverse` 补偿定义，详见 [§2.3.1](#231-execute_write-) | Write+Edit | L1-L2 |
| 6 | `call_api` | 调用外部 API（ERP 同步、HTTP 请求） | Bash | L1-L2 |
| 7 | `send_message` | 向 IM 渠道发送消息（钉钉/企微/飞书），支持文本 + 卡片 + 卡片更新（update_card），详见 [§6.9](#69-ux-im-) | 终端输出 | L1 |
| 8 | `schedule_task` | 登记定时/延迟任务，强制唯一键约束（Upsert by `user_id + intent_type`），详见 [§2.3.2](#232-schedule_task-) | CronCreate | L2 |

#### 2.3.1 `execute_write` 补偿原语（Sagas 模式）

```json
{
  "table": "daily_reports",
  "operation": "insert",
  "data": {"employee": "张三", "order_id": "WO-2026-001", "hours": 8, "date": "2026-06-26"},
  "reverse": {
    "table": "daily_reports",
    "operation": "delete",
    "condition": {"employee": "张三", "order_id": "WO-2026-001", "date": "2026-06-26"}
  }
}
```

> **设计约束**：每个 `execute_write` 的 `reverse` 字段为 **必填项**。ActionExecutor 在多步操作中会自动收集所有已执行步骤的 `reverse` 定义；当任一步骤失败时，按逆序执行补偿操作。不依赖外部 API（2PC/分布式事务），而是利用 `field_history.value_old` 自动生成逆写 SQL。详见 [§5.2](#52-sagas-field_history)。

#### 2.3.2 `schedule_task` 幂等约束

```json
{
  "scope_id": "global",
  "intent_type": "check_shortage_hourly",
  "user_id": "zhangsan",
  "cron": "0 * * * *",
  "action_plan": {...}
}
```

> **设计约束（P1 修正）**：`schedule_task` 使用 `(scope_id, intent_type)` 作为唯一键执行 Upsert，`user_id` 仅作为元数据记录。`scope_id` 的业务语义是"这个任务作用于哪个范围"（如 `global`、`workshop_01`、`production_line_A`），而非"谁创建的"。
>
> **为什么不用 `(user_id, intent_type)`**：如果张三和李四都为同一个车间配置了"每小时检查缺料"的定时任务，`user_id` 不同会导致数据库里出现两条功能重复的 Cron Job。用 `scope_id` 代替 `user_id` 确保同一作用域下相同意图只存在一个活跃任务。

---

### 2.4 SQL 安全沙箱（`query_data` 三级防护）

`query_data` 是唯一暴露 SQL 给 LLM 的原语，必须经受三级安全校验：

#### 第一级：AST 语法树白名单校验

```
LLM 生成的 SQL
    │
    ▼
sqlglot.parse(SQL) → AST
    │
    ├─→ 检查根节点类型：仅允许 SELECT / WITH
    ├─→ 拒绝包含：INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE
    ├─→ 拒绝包含：SELECT ... INTO (通过 INTO 子句检测拦截)
    ├─→ 拒绝包含：COPY, \copy (psql 元命令)
    ├─→ 拒绝包含：自定义函数调用 (防止 SELECT malicious_func())
    ├─→ 拒绝包含：FOR UPDATE / FOR SHARE / NOWAIT / SKIP LOCKED
    │   （防止在只读沙箱中对行加排他锁，阻塞高频报工写入）
    │
    ▼
通过 → 进入第二级
拒绝 → 返回错误："SQL 包含不允许的操作：{具体原因}"
```

#### 第二级：运行时资源限制

```sql
-- 在每条 query_data SQL 执行前，自动注入前缀
SET LOCAL statement_timeout = 3000;   -- 单次查询硬性限制 3 秒
SET LOCAL max_parallel_workers = 0;   -- 禁止并行扫描，避免抢资源
```

如果 SQL 超时，向 LLM 返回：

```json
{
  "error": "查询超时（>3秒）",
  "hint": "请添加更精确的 WHERE 条件，或使用 aggregate_data 先做预聚合",
  "table_hint": "可用索引字段：daily_reports(date, employee, order_id); work_orders(order_id, status)"
}
```

#### 第二级半：Cost Guard 执行代价防御（P0）

Row Guard 拦截的是"返回行数多"的查询，但**行数少 ≠ 性能好**。一条涉及 5 表 JOIN 且无索引命中的 SQL 可能只返回 10 行，但 PostgreSQL 引擎扫描了几百万行做 Hash Join，直接把 CPU 拉满。

```python
COST_HARD_LIMIT = 50000.0  # 压测得出的安全阈值，需要在实际数据库上校准

def check_cost(plan: dict) -> None:
    """从 EXPLAIN (FORMAT JSON) 结果中提取 Total Cost，超阈值直接拒绝。"""
    total_cost = plan[0]["Plan"]["Total Cost"]
    if total_cost > COST_HARD_LIMIT:
        raise QueryRejectedError(
            f"查询执行代价过高（{total_cost:.0f}，阈值 {COST_HARD_LIMIT}），"
            f"可能缺少索引或引发全表扫描。请简化查询或添加 WHERE 条件。"
        )

# 在 execute_query 中，EXPLAIN 返回的 plan 同时用于 Row Guard 和 Cost Guard
plan = conn.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
estimated_rows = parse_plan_rows(plan)
check_cost(plan)  # Cost Guard
```

> **阈值校准**：`COST_HARD_LIMIT` 初始设为 50000.0，实现后在生产数据库上跑一组 benchmark（典型查询 + 毒药查询）校准。建议 Phase 7a 先加监控日志，观察 2 周后锁定阈值。

#### 第三级：Row Guard 行数防御

```python
ROWS_SOFT_LIMIT = 200   # 超过此值不返回原始数据，返回元数据引导
ROWS_HARD_LIMIT = 5000  # 超过此值直接拒绝（任何查询都不可超过）

def execute_query(sql: str) -> dict:
    # 1. EXPLAIN 预估行数（低成本）
    plan = conn.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
    estimated_rows = parse_plan_rows(plan)

    if estimated_rows > ROWS_HARD_LIMIT:
        raise QueryRejectedError(
            f"预估返回 {estimated_rows} 行，超过硬限制 {ROWS_HARD_LIMIT}。请缩小查询范围。"
        )

    # 2. 先用 COUNT(*) 取实际行数（带 timeout 防护）
    count = conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) _sub")).scalar()

    if count > ROWS_SOFT_LIMIT:
        # 不返回数据，返回元数据引导 LLM
        return {
            "truncated": True,
            "total_rows": count,
            "sample": fetch_sample(sql, limit=5),  # 返回 5 行样本
            "columns": [...],
            "guidance": (
                f"查询返回 {count} 条记录（超过单次展示上限 {ROWS_SOFT_LIMIT}）。"
                f"请选择以下策略之一：\n"
                f"1. 调用 aggregate_data 对结果进行分组/聚合\n"
                f"2. 添加更精确的 WHERE 条件（日期、工单号、员工名）\n"
                f"3. 如果确实需要全量数据，分页拉取（每次 {ROWS_SOFT_LIMIT} 条）"
            ),
        }

    # 3. 行数安全，返回全部结果
    return {"truncated": False, "total_rows": count, "data": fetch_all(sql)}
```

#### Row Guard 的 LLM 行为引导示例

```
用户："把今年的报工数据核对一下"
Agent → query_data("SELECT * FROM daily_reports WHERE date >= '2026-01-01'")
      ← {
          "truncated": true,
          "total_rows": 4500,
          "guidance": "查询返回 4500 条记录（超过单次展示上限 200）..."
        }
Agent → 理解指引，自动调整策略：
        aggregate_data(daily_reports, group_by="month", sum="hours")
      ← { "2026-01": 3200, "2026-02": 2800, ... }
Agent → "今年 1-6 月共报工 XXX 小时，按月分布如下..."
```

这确保 LLM 被"引导"而非被"拒绝"——Row Guard 不给死胡同，给下一步方向。

---

### 2.5 语义快捷方式（保留高频组合）

（原 §2.4，内容不变）

| 快捷方式 | 等价原语组合 | 原因 |

某些高频操作如果每次都由 LLM 推理多步组合，token 消耗大且容易出错。保留少量快捷方式：

| 快捷方式 | 等价原语组合 | 原因 |
|----------|-------------|------|
| `submit_daily_report` | query_data(查员工ID) → execute_write(插入daily_reports) → execute_write(刷新物化视图) | 每天几十次，最高频 |
| `sync_erp_data` | call_api(IN3/工单) → call_api(IN3/BOM) → call_api(IN3/库存) → execute_write(写入本地) | 多 API 串联，逻辑固定 |
| `check_shortage` | query_data(缺料SQL) → aggregate_data(按工单分组) → send_message(推送告警) | 多原语 + 消息推送 |

---

## 三、编排层：混合路由（快路径 + LLM 兜底）

### 3.1 架构

```
用户输入（自然语言 / IM 消息 / 界面操作）
        │
        ▼
  ┌─────────────────────┐
  │  IntentRouter        │  ← 已有，扩展执行意图
  │  正则快路径 + LLM兜底  │
  └──────┬──────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 查询意图    执行意图
 (已有)      (新增)
    │         │
    ▼         ▼
HubController  ActionDispatcher ← 新增
(已有)         │
    │         ├─→ 快捷方式表匹配？→ 直接执行
    │         └─→ 否 → ReAct Agent → LLM 推理原语组合
    │                    │
    ▼                    ▼
 渲染结果            ActionExecutor ← 新增
                    │
              ┌─────┼─────┐
              ▼     ▼     ▼
           L0自动  L1确认  L2审批
           (直接)  (弹窗)  (Decision卡片)
```

### 3.2 ActionDispatcher（新增）

```python
# core/agent/action_dispatcher.py

class ActionDispatcher:
    """处理执行类意图，分发到快捷方式或 ReAct Agent"""

    # 快捷方式映射表
    _SHORTCUTS = {
        "submit_daily_report": {...},
        "sync_erp_data": {...},
        "check_shortage": {...},
    }

    def dispatch(self, intent: dict, ctx: ExecutionContext) -> ActionPlan:
        """
        1. 意图有快捷方式 → 生成确定性 ActionPlan
        2. 意图无快捷方式 → 调用 ReAct Agent 推理原语组合
        3. 返回 ActionPlan（步骤列表 + 每步的风险等级）
        """
```

### 3.3 ActionPlan 结构

```python
@dataclass
class ActionStep:
    tool: str           # 原语名称
    params: dict        # 参数
    risk_level: int     # L0/L1/L2
    description: str    # 人类可读描述（用于确认界面）
    depends_on: str     # 依赖的前一步（用于顺序控制）

@dataclass
class ActionPlan:
    steps: list[ActionStep]
    generated_by: str   # "shortcut" | "react"
    total_risk: int     # max(steps.risk_level)
```

---

## 四、安全层：三级风险分级

### 4.1 风险定义

| 级别 | 名称 | 示例 | 行为 |
|------|------|------|------|
| **L0** | 只读 | 查询数据库、读文件、统计聚合 | **自动执行**，无需任何确认 |
| **L1** | 低风险写 | 写入日报、同步 ERP 数据、发送消息 | **语义确认**：显示"将执行：[人类可读描述]"，用户确认后执行 |
| **L2** | 高风险写 | 创建工单、修改标准工时、批量删除 | **审批确认**：生成 Decision 卡片，推送到指挥中心，必须有 supervisor 角色审批 |

### 4.2 确认消息设计

**L1 语义确认（轻量，不阻塞操作流）：**

```
┌─────────────────────────────────────────────┐
│  ⚡ 即将执行以下操作：                        │
│                                             │
│  给 张三 在 WO-2026-001 上报工 8.0 小时      │
│  日期：2026-06-26                           │
│                                             │
│  [确认执行]  [取消]                          │
└─────────────────────────────────────────────┘
```

**L2 审批确认（走现有 Decision 管道）：**

```
Priority Engine 生成 Level 4 Decision：
  title: "批量修改标准工时"
  description: "Agent 请求将冲剪机系列 12 个工序的标准工时统一上调 15%"
  suggested_actions:
    - approve: → ActionExecutor 执行批量 UPDATE
    - reject:  → 驳回，记录驳回原因
```

### 4.3 风险判定规则

```python
def assess_risk(tool: str, params: dict, user_role: str) -> int:
    """判定操作风险等级"""
    if tool in ("query_data", "search_entities", "read_file", "aggregate_data"):
        return 0  # L0: 所有只读操作

    if tool == "send_message":
        return 1  # L1: 发消息需确认

    if tool == "execute_write":
        # 写入日报/刷新视图 → L1；修改关键表 → L2
        if params.get("table") in ("daily_reports", "materialized_views"):
            return 1
        return 2  # employees, work_orders, standard_time_units 等

    if tool == "call_api":
        if params.get("operation") == "sync":
            return 1  # 同步是安全的
        return 2      # 其他 API 调用

    if tool == "schedule_task":
        return 2  # 定时任务需要审批

    return 1  # 默认 L1
```

---

## 五、ActionExecutor：闭环的最后一环

### 5.1 职责

```
Decision (status=approved) ───→ ActionExecutor ───→ 真实操作
                                      │
                                ┌─────┼─────┐
                                ▼     ▼     ▼
                           execute_write  call_api  send_message
                                │     │     │
                                ▼     ▼     ▼
                           field_history   sync_queue   消息回执
                                │
                                ▼
                          失败？→ Sagas 补偿回滚
                          (自动读取 field_history.value_old 逆写)
```

### 5.2 Sagas 补偿模式：利用 field_history 自动回滚

#### 问题

v1.0 方案在"多步操作部分失败"时声明"已成功的步骤不回滚，失败步骤记录到死信队列"。这在工厂场景下会产生**数据不一致窗口**：

```
Step 1: execute_write → 本地工单状态改为"生产中"  ✓
Step 2: call_api → 调用 ERP 同步接口            ✗ ERP 挂了
结果: 本地 ="生产中", ERP ="待排产" → 排产引擎基于脏数据计算
```

#### 解决：逆序补偿，无需额外补偿表

每个 `execute_write` 的 `reverse` 字段已经定义了逆操作（见 [§2.3.1](#231-execute_write-)）。ActionExecutor 在执行中自动收集补偿链，失败时逆序执行：

```python
class ActionExecutor:
    def __init__(self, db: Session):
        self.db = db
        self.primitives = PrimitiveRegistry(db)
        self._compensations: list[CompensationAction] = []  # 补偿链

    def execute(self, decision, action) -> ExecutionResult:
        plan = ActionPlan.from_payload(action.payload)
        self._compensations = []

        try:
            for i, step in enumerate(plan.steps):
                result = self.primitives.call(step.tool, step.params)

                if not result.success:
                    # ── 失败 → 立即启动补偿回滚 ──
                    self._rollback(decision)
                    return ExecutionResult(
                        success=False,
                        error=f"步骤 {i+1}/{len(plan.steps)} 失败: {result.error}",
                        compensated_steps=len(self._compensations),
                    )

                # ── 成功 → 记录补偿信息 ──
                self._record_compensation(step, result)

            # ── 全部成功 → 清空补偿链（提交生效） ──
            self._compensations.clear()
            decision.status = "executed"
            self.db.commit()
            return ExecutionResult(success=True)

        except Exception as e:
            self._rollback(decision)
            raise

    def _record_compensation(self, step: ActionStep, result):
        """每步成功后，根据执行结果构造补偿操作"""
        if step.tool == "execute_write":
            # 直接从 step.params.reverse 取逆操作
            self._compensations.append(CompensationAction(
                tool="execute_write",
                params=step.params.get("reverse"),
            ))
        elif step.tool == "call_api":
            # API 操作通常无补偿（外部系统不保证幂等）
            # 仅记录到 sync_queue 供人工处理
            self._compensations.append(CompensationAction(
                tool="sync_queue_record",  # 标记需要人工补偿
                params={"api_call": step.params, "result": result},
            ))

    def _rollback(self, decision):
        """逆序执行补偿链（LIFO）"""
        compensated = 0
        # 逆序遍历已记录的补偿操作
        for comp in reversed(self._compensations):
            try:
                if comp.tool == "execute_write":
                    # execute_write 的 reverse 本身就是合法的 execute_write 参数
                    self.primitives.call("execute_write", comp.params)
                    compensated += 1
                elif comp.tool == "sync_queue_record":
                    # API 操作无法自动回滚，写入死信队列等人工处理
                    self._write_dead_letter(comp.params)
            except Exception as e:
                # 补偿本身也失败 → 这是最坏情况，记录详细日志
                self._log_critical_rollback_failure(comp, e)

        decision.status = "failed"
        decision.decision_note = (
            f"执行失败，已自动补偿 {compensated}/{len(self._compensations)} 步。"
            f"剩余步骤已写入死信队列。"
        )
        self.db.commit()
```

#### field_history 辅助自动逆写（含乐观锁防并发覆盖 — P1）

`execute_write` 在执行前会把 `value_old` 写入 `field_history`。如果 `reverse` 字段缺失（兼容旧调用），回滚引擎可以自动从 `field_history` 查询旧值并构造逆写：

```python
def auto_generate_reverse(table: str, record_id: str, db_time_at_execution: str) -> dict:
    """从 field_history 读取 value_old 自动生成逆写参数。

    防并发覆盖（P1）：condition 必须携带 updated_at 时间戳。
    如果回滚时发现记录已被其他人修改（updated_at 不匹配），
    说明有并发写入，放弃自动回滚，降级到 critical_rollback_failure。
    """
    old_values = query_field_history(table, record_id, limit=1)
    if old_values:
        return {
            "table": table,
            "operation": "update",
            "condition": {
                "id": record_id,
                "updated_at": db_time_at_execution,  # 乐观锁：确保期间没被别人改过
            },
            "data": old_values,
        }
    raise CompensationError(f"无法自动生成逆写: {table}.{record_id} 无历史记录")

# 回滚执行时，先检查 condition 是否匹配
def safe_reverse_write(reverse_params: dict) -> bool:
    """执行逆写，带乐观锁检查。返回 True 表示补偿成功。"""
    table = reverse_params["table"]
    condition = reverse_params["condition"]
    # 先 SELECT 检查当前 updated_at 是否和条件匹配
    current = conn.execute(text(f"SELECT updated_at FROM {table} WHERE id = :id"), condition).fetchone()
    if not current or str(current[0]) != str(condition.get("updated_at")):
        # 并发修改已发生，放弃自动回滚
        write_dead_letter(reverse_params, reason="乐观锁不匹配：记录已被其他操作修改")
        return False
    # 匹配，执行逆写
    execute_write(reverse_params)
    return True
```

> **前提**：核心业务表（`work_orders`、`daily_reports`、`production_plan`）需要有 `updated_at` 字段。Phase 7a 第一步先通过 DDL 迁移加上该字段。

### 5.3 与现有 DecisionService 的关系

不替换 `DecisionService`，而是作为它的**下一站**：

```python
# api/services/decision_service.py (修改后的 execute_action)

def execute_action(self, decision_id, action, idempotency_key, user, note, payload):
    # ... 现有状态更新逻辑保持不变 ...

    if dec.status in ("approved", "executing"):
        # 新增：调用 ActionExecutor 真正执行
        from api.services.action_executor import ActionExecutor
        executor = ActionExecutor(self.db)
        result = executor.execute(dec, payload.get("action_plan"))
        return {
            "success": result.success,
            "decision_status": dec.status,
            "outcome_id": result.outcome_id,
        }
```

---

## 六、IM 集成：钉钉优先

### 6.1 为什么钉钉优先

| 原因 | 说明 |
|------|------|
| 工厂普及率 | 制造业钉钉渗透率远超企微/飞书 |
| 技术门槛低 | `dingtalk-stream` Python SDK 用 WebSocket，不需公网域名 |
| SDK 可用性 | 已有成熟的 Python 流式 SDK |
| 用户习惯 | 工厂主管已经用钉钉审审批 |

### 6.2 架构

```
钉钉群                   你的系统
───────                 ─────────
@bot 查缺料     ──→    POST /api/im/dingtalk/webhook
                        │
                        ▼
                  DingTalkAdapter.receive()
                        │
                        ▼
                  IntentRouter.route()
                        │
                  ┌─────┴─────┐
                  ▼           ▼
              查询意图(直接)  执行意图(需审批)
                  │           │
                  ▼           ▼
              HubController  ActionDispatcher
                  │           │
                  ▼           ▼
              send_message  ActionExecutor
                  │           │
                  ▼           ▼
"缺料如下：       ←── 钉钉回复消息
WO-001 铜排 ×3
WO-003 端子 ×12"
```

### 6.3 模块设计

```
core/im/
├── __init__.py
├── base.py              # MessageAdapter 抽象基类
├── dingtalk.py          # 钉钉 Stream 模式适配器
├── message_types.py     # 统一消息格式（文本/卡片/审批）
└── pairing.py           # 配对授权管理

api/routers/
└── im.py                # IM webhook 入口 + 平台管理 API
```

### 6.4 统一消息接口

```python
# core/im/base.py
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class IMessage:
    """统一消息格式，所有平台适配器对内都是这个格式"""
    platform: str          # "dingtalk" | "wecom" | "feishu"
    chat_id: str           # 群/会话 ID
    sender_id: str         # 发送者 ID
    sender_name: str       # 发送者名称
    text: str              # 消息正文
    is_mention_bot: bool   # 是否 @了机器人
    raw: dict              # 平台原始消息（调试用）

class MessageAdapter(ABC):
    """IM 平台适配器抽象基类"""

    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def stop(self): ...
    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> str: ...
    @abstractmethod
    async def send_card(self, chat_id: str, card: dict) -> str: ...
```

### 6.5 钉钉适配器

```python
# core/im/dingtalk.py
import dingtalk_stream

class DingTalkAdapter(MessageAdapter):
    """钉钉 Stream 模式适配器

    优势：WebSocket 长连接，不需要公网 IP/域名/HTTPS 证书
    前提：钉钉开放平台创建应用 → 获取 ClientID + ClientSecret
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = None
        self._message_handler: Callable = None  # 收到消息时回调

    async def start(self):
        """启动 WebSocket 连接"""
        credential = dingtalk_stream.Credential(self.client_id, self.client_secret)
        self._client = dingtalk_stream.DingTalkStreamClient(credential)
        self._client.register_callback(
            dingtalk_stream.ChatbotMessage.TOPIC,
            self._on_message
        )
        await self._client.start()

    async def _on_message(self, msg: dingtalk_stream.ChatbotMessage):
        """收到钉钉消息 → 转换为 IMessage → 回调业务层"""
        im_msg = IMessage(
            platform="dingtalk",
            chat_id=msg.conversation_id,
            sender_id=msg.sender_id,
            sender_name=msg.sender_nick,
            text=msg.text.strip(),
            is_mention_bot=True,  # 群聊中只有 @bot 的消息才会被回调
            raw=msg,
        )
        if self._message_handler:
            await self._message_handler(im_msg)

    async def send_text(self, chat_id: str, text: str) -> str:
        """通过 Webhook 回复消息"""
        # ...
```

### 6.6 配对授权（从 INA 学习）

```
1. 员工在钉钉群 @bot："今天缺料情况"
2. Bot 检查 sender_id 是否在 assistant_users 表中
   ├── 已授权 → 正常处理
   └── 未授权 → 回复"你尚未授权，配对码：A7X3"
3. 管理员在 Web 后台 [系统设置 → IM 管理] 看到待审批配对
4. 管理员批准 → sender_id 写入 assistant_users
5. 后续该员工的所有消息正常处理
```

### 6.7 DB 表设计

```sql
-- IM 平台配置（每个平台一条记录）
CREATE TABLE im_platforms (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,       -- 'dingtalk' | 'wecom' | 'feishu'
    enabled INTEGER DEFAULT 0,
    config TEXT DEFAULT '{}',     -- JSON: {client_id, client_secret, webhook_url, ...}
    status TEXT DEFAULT 'created',-- created/starting/running/stopped/error
    last_connected TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- 授权用户映射（IM 用户 ↔ 系统用户）
CREATE TABLE im_authorized_users (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    platform_user_name TEXT,
    employee_id TEXT,             -- 关联 employees 表
    role TEXT DEFAULT 'operator', -- operator/supervisor/admin
    authorized_at TEXT,
    UNIQUE(platform, platform_user_id)
);

-- 配对码（临时授权用）
CREATE TABLE im_pairing_codes (
    code TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending/approved/rejected/expired
    created_at TEXT,
    expires_at TEXT
);
```

### 6.8 API 路由

```python
# api/routers/im.py

# ── Webhook 入口（钉钉回调） ──
@router.post("/api/im/dingtalk/webhook")
async def dingtalk_webhook(request: Request):
    """钉钉消息回调。由 DingTalkAdapter 内部处理，
    此端点用于健康检查 & 接收离线的 Stream 事件。"""
    ...

# ── 平台管理 ──
@router.post("/api/im/platforms")
async def register_platform(platform: str, config: dict):
    """注册/更新 IM 平台配置"""
    ...

@router.post("/api/im/platforms/{platform}/start")
async def start_platform(platform: str):
    """启动 IM 平台适配器"""
    ...

@router.get("/api/im/platforms/{platform}/status")
async def get_platform_status(platform: str):
    """查询 IM 平台状态"""
    ...

# ── 配对管理 ──
@router.get("/api/im/pairings")
async def get_pending_pairings():
    """获取待审批配对列表"""
    ...

@router.post("/api/im/pairings/{code}/approve")
async def approve_pairing(code: str):
    """批准配对"""
    ...
```

### 6.9 IM 流式状态卡片（UX 反压设计）

#### 问题

ReAct Agent 执行复杂分析时可能需要 10-30 秒。如果用户发消息后系统沉寂 30 秒，用户会认为 Bot 挂了 → 重复发送 → 并发冲突 + 重复处理。

#### 解决：渐进式状态卡片

`send_message` 原语支持三种消息模式：

| 模式 | 方法 | 用途 |
|------|------|------|
| `text` | `send_text()` | 普通文本回复（最终结果） |
| `card` | `send_card()` | 富文本卡片（审批请求 / 结构化报告） |
| `update_card` | `update_card(msg_id, new_content)` | 增量更新已有卡片（流式进度） |

#### 执行时序

```
时间轴   用户视角（钉钉）                        系统内部
─────────────────────────────────────────────────────────────
0s      @bot "检查 WO-001 为什么延期"
        ─────────────────────────────────→  IntentRouter.route()
                                           ↓
1s      ┌─────────────────────────┐
        │ 🤖 正在分析您的请求...    │  ←──  send_card(thinking_card)
        └─────────────────────────┘       ActionDispatcher → ReAct Agent
                                           ↓
3s      ┌─────────────────────────┐
        │ 🔍 正在读取工单进度...   │  ←──  update_card("正在读取工单进度...")
        │ ✅ 工单进度已获取        │       ReAct step 1: query_data(工单) → 完成
        │ 🔍 正在检查缺料情况...   │       ReAct step 2: aggregate_data(缺料) → 进行中
        └─────────────────────────┘
                                           ↓
8s      ┌─────────────────────────┐
        │ 🔍 正在检查缺料情况...   │
        │ ✅ 缺料分析已完成        │  ←──  ReAct step 2 完成
        │ 🔍 正在分析人员工时...   │       ReAct step 3 开始
        └─────────────────────────┘
                                           ↓
15s     WO-001 延期原因分析：              ReAct → 最终答案
        1. 铜排(MCU-001)缺料 3 天
        2. 张三年假，替代人员效率低 30%
        ...                       ←──  send_text(最终结果)
                                           ↓
                                       同时 update_card → 移除进度卡片
```

#### 实现要点

```python
class MessageAdapter(ABC):
    @abstractmethod
    async def send_card(self, chat_id: str, card: dict) -> str:
        """发送卡片消息，返回 message_id 供后续更新"""
        ...

    @abstractmethod
    async def update_card(self, chat_id: str, message_id: str, card: dict) -> None:
        """增量更新已有卡片的内容"""
        ...

# DingTalkAdapter 实现
class DingTalkAdapter(MessageAdapter):
    async def send_card(self, chat_id, card):
        result = await self._client.send(
            msg_type="action_card",  # 钉钉的交互式卡片
            content=card,
        )
        return result["processQueryKey"]  # 返回 msg_id

    async def update_card(self, chat_id, message_id, card):
        await self._client.update_card(
            out_track_id=message_id,
            content=card,
        )
```

#### 进度卡片的触发时机

ReAct Agent 每完成一步 observation 后，自动调用 `send_message("update_card", ...)` 刷新 IM 状态卡片：

```python
# ReactAgent.run() 内部改造
for step in range(1, self.max_steps + 1):
    # ... 执行工具 ...
    result = self._execute_action(action, ctx)
    observation = {"工具": tool_name, "结果": result}

    # 新增：IM 进度推送
    if self._im_chat_id:
        self._push_progress(self._im_chat_id, step, tool_name, "完成" if result else "失败")

    history.append({"role": "observation", "content": json.dumps(observation, ensure_ascii=False)})
```

> **注意**：IM 进度卡片功能属于 UX 增强，Phase 7d 先实现基础 send_text，Phase 7f 联调时补上流式进度。

---

## 七、与现有系统的集成

### 7.1 修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/agent/tools/__init__.py` | **修改** | 替换为原语注册 |
| `core/agent/tools/primitives.py` | **新建** | 8 个基础原语（含 SQL 沙箱 + Row Guard + Sagas 补偿） |
| `core/agent/tools/shortcuts.py` | **新建** | 3-5 个语义快捷方式 |
| `core/agent/action_dispatcher.py` | **新建** | 执行意图分发 |
| `core/agent/action_plan.py` | **新建** | ActionPlan + ActionStep + CompensationAction 数据结构 |
| `core/agent/risk_engine.py` | **新建** | 三级风险判定 + 置信度→质量等级映射 |
| `core/agent/sql_sandbox.py` | **新建** | SQL AST 校验 + Row Guard + statement_timeout 注入 |
| `core/im/` | **新建** | IM 适配器包（含流式状态卡片支持） |
| `api/services/action_executor.py` | **新建** | Action 执行 + Sagas 补偿回滚 |
| `api/services/decision_service.py` | **修改** | `execute_action` 增加 ActionExecutor 调用 |
| `api/routers/im.py` | **新建** | IM webhook + 管理 API |
| `api/models/im.py` | **新建** | IM 相关 ORM 模型 |
| `api/main.py` | **修改** | 注册 IM router + 启动时启动 IM 适配器 |
| `frontend/src/app/settings/` | **修改** | 设置页面增加 [IM 管理] 标签页 |
| `frontend/src/components/im/` | **新建** | IM 配对审批组件加载中... |
| `frontend/src/components/quality-indicator.tsx` | **新建** | 数据质量等级背景色指示器（按 A-E 级渲染不同背景色） |

### 7.2 不改的部分

- `core/` 下所有业务逻辑模块（`standard_time.py`、`delivery_risk.py` 等）**不动**
- `api/models/event.py`、`api/models/decision.py` **不动**
- `api/routers/events.py`、`api/routers/decisions.py`、`api/routers/actions.py` **不动**（actions 内部增加调用）
- `api/domain/priority_engine.py` **不动**
- 前端页面 **不动**（仅设置页增加 Tab + 新增质量指示器组件）

### 7.3 数据流全景（改后）

```
┌──────────────────────────────────────────────────────────┐
│                      数据入口                              │
│  ERP API  │  Excel  │  自然语言  │  钉钉 @bot  │  手动录入  │
└──────┬───────┬───────┬──────────┬──────────┬──────────┘
       │       │       │          │          │
       ▼       ▼       ▼          ▼          ▼
  ┌────────────────────────────────────────────────────┐
  │                 IntentRouter                         │
  │         正则快路径(80%+) → LLM兜底(<20%)              │
  └─────────┬──────────────────┬───────────────────────┘
            │                  │
     查询意图                 执行意图
            │                  │
            ▼                  ▼
     HubController      ActionDispatcher
     (已有,不变)         (新增)
            │             ├─ 快捷方式 → 直接生成 ActionPlan
            ▼             └─ ReAct → LLM推理原语组合
      QueryBuilder              │
            │                   ▼
            ▼             RiskEngine (新增)
      Analytics          ├─ L0 → 自动执行
            │            ├─ L1 → 语义确认(轻量弹窗)
            ▼            └─ L2 → 生成Decision卡片
      渲染结果                  │
            │                   ▼
            │            ActionExecutor (新增)
            │             ├─ execute_write
            │             ├─ call_api
            │             ├─ send_message
            │             └─ schedule_task
            │                   │
            │         ┌─────────┼─────────┐
            │         ▼         ▼         ▼
            │    PostgreSQL  ERP API  钉钉消息
            │         │         │         │
            │         ▼         ▼         ▼
            │    field_history  sync_queue  消息回执
            │
            ▼
  ┌────────────────────────────────────────────────────┐
  │              前端展示层（不变）                        │
  │  指挥中心  │  生产中心  │  设备中心  │  人员中心  │ ... │
  └────────────────────────────────────────────────────┘
```
```

---

## 八、置信度 → 数据质量联动（AI 原生数据治理）

### 8.1 核心思想

大模型在生成 `execute_write` 的参数时，根据其推理的确定性，携带一个 `confidence` 字段。该字段自动映射到现有 ontology.json 中定义的数据质量等级（A/B/C/D/E），实现 **"AI 自己标注自己生成的数据有多可信"**。

### 8.2 置信度 → 质量等级映射

```
LLM 生成的 confidence    数据来源                          → 质量等级
─────────────────────    ────────────────────────────────    ──────
1.0                      Shortcut 路径（确定性规则）         → A 级（实测）或 B 级（推导）
0.8 - 0.99               LLM ReAct 推理，有数据支撑          → C 级（IE 估计）
0.5 - 0.79               LLM ReAct 推理，推测/外推            → D 级（默认值）
< 0.5                    无有效数据，仅 LLM 先验知识           → E 级（未验证）
```

### 8.3 实现链路

```
Agent 生成 execute_write 参数
    ↓
{
  "table": "work_orders",
  "operation": "update",
  "condition": {"order_id": "WO-2026-001"},
  "data": {"standard_hours": 120.0},
  "confidence": 0.65,          ← LLM 自评的置信度
  "reasoning": "基于近 30 天同型号工单实际工时的中位数推算"
}
    ↓
execute_write 执行时：
  1. 写入数据到目标表
  2. 写入 field_history（含 confidence + reasoning）
  3. 自动映射质量等级：
     confidence >= 1.0  → quality_grade = "A"  (if shortcut) / "B" (if derived)
     confidence >= 0.8  → quality_grade = "C"
     confidence >= 0.5  → quality_grade = "D"
     confidence <  0.5  → quality_grade = "E"
  4. quality_grade 作为 field_history 的附加字段持久化
    ↓
前端 QualityIndicator 组件根据 quality_grade 渲染背景色：
  A 级：无背景色（标准数据）
  B 级：无背景色
  C 级：浅蓝底（提示：IE 估计）
  D 级：浅黄底（提示：系统默认/推测）
  E 级：淡红底（警告：未验证 AI 生成数据）
```

### 8.4 置信度判定来源

| 来源 | confidence | 说明 |
|------|-----------|------|
| Shortcut 路径（如 `submit_daily_report`） | `1.0` | 确定性规则，不需要 LLM 介入 |
| ReAct Agent step，`action.confidence` 由 LLM 输出 | `0.0-1.0` | LLM 在生成 ActionPlan 时，为每个 step 输出置信度 |
| 用户在 L1/L2 确认时手动调整 | 可覆盖 | 用户在确认界面可以上调或下调 confidence |

### 8.5 前端质量指示器组件

```tsx
// frontend/src/components/quality-indicator.tsx

interface QualityIndicatorProps {
  grade: 'A' | 'B' | 'C' | 'D' | 'E';
  value: string | number;
}

const GRADE_STYLES: Record<string, string> = {
  A: '',                                   // 标准，无需指示
  B: '',                                   // 标准，无需指示
  C: 'bg-blue-50 dark:bg-blue-950/30',     // 浅蓝：IE 估计
  D: 'bg-yellow-50 dark:bg-yellow-950/30', // 浅黄：默认值/推测
  E: 'bg-red-50 dark:bg-red-950/30',       // 淡红：未验证 AI 生成
};

function QualityIndicator({ grade, value }: QualityIndicatorProps) {
  if (grade === 'A' || grade === 'B') return <span>{value}</span>;

  return (
    <span className={GRADE_STYLES[grade]} title={`数据质量: ${grade}级`}>
      {value}
      <sup className="text-[10px] ml-0.5 opacity-60">{grade}</sup>
    </span>
  );
}
```

### 8.6 对现有 ontology.json 的增量

`config/ontology.json` 的 `meta` 区块增加 `quality_propagation` 规则：

```json
{
  "meta": {
    "quality_propagation": {
      "description": "当推导属性依赖的数据源质量等级较低时，推导结果自动降级",
      "rules": [
        {"if": "any_input_grade >= D", "then": "propagate_max_grade_to_output"},
        {"if": "confidence < 0.5", "then": "mark_as_E_and_notify_supervisor"}
      ]
    }
  }
}
```

---

## 九、错误处理与幂等性

### 9.1 幂等性保证

沿用现有的 `idempotency_key` 机制，扩展到所有写操作：

```python
# ActionExecutor 内
def execute(self, decision, action):
    # 1. 幂等检查
    if decision.idempotency_key == action.payload.get("idempotency_key"):
        return ExecutionResult(success=True, is_replay=True)

    # 2. 乐观锁：status 必须为 'approved' 或 'executing' 才允许执行
    if decision.status not in ("approved", "executing"):
        raise ConflictError(f"Decision {decision.id} 当前状态为 {decision.status}，不可执行")

    # 3. 执行（含 Sagas 补偿，见 §5.2）
    # 4. 成功后设置 idempotency_key 标记
```

### 9.2 失败处理策略（v2.0：Sagas 补偿版）

| 失败场景 | 处理 |
|----------|------|
| **L0 查询失败** | 返回结构化错误给 LLM（含 hint + 表索引信息），LLM 调整查询重试（最多 3 次） |
| **SQL 超时（>3秒）** | 返回 timeout 错误 + 索引提示 + 引导 LLM 添加 WHERE 条件或使用 aggregate_data |
| **Row Guard 触发（>200行）** | 返回元数据（total_rows + sample + guidance），引导 LLM 聚合或筛选 |
| **L1 单步写入失败** | 单步操作无补偿需求，返回错误详情 + 保留用户输入以便重试 |
| **L2 API 调用失败** | 写入 sync_dead_letter 表，通知管理员可手动重试 |
| **多步操作部分失败** | **自动 Sagas 补偿回滚**（见 §5.2）：逆序执行已成功步骤的 reverse 操作；DB 写入可自动回滚，API 操作写入死信队列等人工补偿 |
| **补偿本身也失败（最坏情况）** | 记录 `critical_rollback_failure` 到独立日志表，通知 admin + supervisor，需要人工介入 |

---

## 十、实现阶段

| Phase | 内容 | 依赖 | 预计 |
|-------|------|------|------|
| **Phase 7a** | 原语重构：8 个基础工具（含 SQL 沙箱 + Row Guard + 补偿字段） + 3 个快捷方式 | 无 | 2-3 天 |
| **Phase 7b** | RiskEngine + ActionPlan + ActionDispatcher | 7a | 1-2 天 |
| **Phase 7c** | ActionExecutor（含 Sagas 补偿回滚） + 与 DecisionService 集成 | 7b | 2-3 天 |
| **Phase 7d** | IM 适配器 + 钉钉 Stream 集成（基础 send_text） | 无 | 2-3 天 |
| **Phase 7e** | IM 配对授权 + 设置页 Tab + QualityIndicator 组件 | 7d | 1-2 天 |
| **Phase 7f** | 联调测试 + IM 流式状态卡片 + 文档 | 7a-7e | 2-3 天 |

Phase 7a-7c 和 7d-7e 可并行开发。

---

## 十一、风险与应对（v2.0 更新）

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| LLM 生成的 SQL 有语法错误 | 中 | 查询失败 | AST 校验层（sqlglot）+ 结构化错误提示 + 自动重试（最多 3 次） |
| LLM 生成的 SQL 性能毒药 | 中 | 数据库负载飙升 | `SET LOCAL statement_timeout=3000` + 禁止并行扫描 + Row Guard 硬限制 5000 行 |
| `query_data` 返回海量数据 | 高 | LLM context 冲垮 + token 爆炸 | Row Guard 软限制 200 行，返回元数据引导而非拒绝 |
| LLM 生成的 ActionPlan 不合理 | 中 | 执行错误 | L1/L2 确认机制兜底 + 每步含人类可读 description |
| 多步操作部分失败导致数据不一致 | 中 | 数据血缘污染 | Sagas 补偿模式：`execute_write` 强制附带 `reverse` 定义，失败时自动逆序回滚 |
| 补偿本身也失败（最坏情况） | 低 | 需人工介入 | `critical_rollback_failure` 日志表 + admin/supervisor 双通知 |
| LLM 重复注册定时任务 | 中 | 僵尸任务堆积 | `schedule_task` 采用 Upsert by `(user_id, intent_type)` |
| 钉钉 Stream 断连 | 低 | IM 不可用 | 自动重连 + 状态监控 |
| LLM token 消耗失控 | 中 | 成本 | 快捷方式映射表命中率目标 80%+ + Row Guard 阻止大返回 |
| AI 生成数据不可信 | 中 | 数据质量退化 | 置信度→质量等级联动 + field_history 记录 reasoning + 前端质量指示器 |
| 用户重复发送 IM 消息（以为 Bot 挂了） | 中 | 并发冲突 | IM 流式状态卡片：1 秒内推送进度卡，持续更新步骤状态 |
