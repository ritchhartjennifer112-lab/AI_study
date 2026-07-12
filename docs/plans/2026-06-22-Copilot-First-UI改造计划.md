# Copilot-First UI 全量改造计划

**日期**: 2026-06-22  
**基于**: 当前 `core/agent/` 架构 + 21 个 Streamlit 页面  
**总工期**: 约 4 周（20 个工作日）  
**目标**: 将传统目录式界面改造为"对话即界面"的 AI 原生交互模式

---

## 1. 改造目标

### 1.1 现状问题

当前系统有 21 个固定页面，采用传统菜单式组织：

- 用户想找信息时，需要先判断该进哪个页面
- 多个页面之间存在数据割裂（如人员维度、工单进度、效率看板都涉及工时，但入口不同）
- Copilot 虽然已嵌入各页面底部，但仍是"辅助输入框"，没有成为主入口
- 新增分析视图需要新增页面，扩展成本高

### 1.2 目标形态

用户打开系统后，主界面只有一个 Copilot 输入框 + 动态页签区：

```
┌─────────────────────────────────────────────┐
│ 🤖 工厂 Copilot                              │
│ [ 用户在此输入自然语言问题... ]              │
├─────────────────────────────────────────────┤
│ 📊 张三本周报工  |  📈 WO-001延期分析  |  + │
├─────────────────────────────────────────────┤
│                                             │
│  [ 当前页签的动态分析内容 ]                  │
│                                             │
└─────────────────────────────────────────────┘
```

每个页签都是 AI 根据用户问题即时渲染的分析界面，不是预定义页面。

### 1.3 设计原则

1. **对话即界面**：自然语言是主要交互方式
2. **渐进替代**：不一次性删除现有页面，先让 Copilot 覆盖高频场景
3. **模板约束**：AI 只选择渲染模板 + 填充数据，避免输出不稳定
4. **上下文连续**：支持多轮对话、页签对比、二次分析
5. **保留必要入口**：复杂配置、批量录入等场景保留固定页面

---

## 2. 新架构设计

### 2.1 整体架构

```
用户输入（自然语言）
    │
    ▼
┌─────────────────────────────────────┐
│  Copilot Hub（pages/16_智能助理.py） │  ← 主入口：输入框 + 页签管理
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  意图路由器（core/agent/intent_router.py） │  ← 识别：分析 / 打开页面 / 录入 / 执行流程
└────────┬────────────────────────────┘
         │
    ┌────┴────┬────────────┬──────────────┐
    ▼         ▼            ▼              ▼
  分析模板   页面跳转      表单填充       工作流执行
  （新）    （已有）       （已有）        （已有）
    │
    ▼
┌─────────────────────────────────────┐
│  视图渲染器（core/agent/renderer.py） │  ← 根据模板生成 Streamlit 组件
└─────────────────────────────────────┘
```

### 2.2 核心新增模块

| 模块 | 文件 | 职责 |
|------|------|------|
| Copilot Hub | `pages/16_智能助理.py` | 主入口、输入框、页签容器 |
| 分析模板库 | `core/agent/templates/` | 定义可复用的分析视图模板 |
| 视图渲染器 | `core/agent/view_renderer.py` | 把模板 + 数据渲染为 UI |
| 页签管理器 | `core/agent/tab_manager.py` | 创建/切换/关闭/保存页签状态 |
| 分析意图扩展 | `core/agent/intent_router.py` | 识别具体分析类型（趋势/对比/归因/列表） |
| 查询构造器 | `core/agent/query_builder.py` | 把分析意图转换为 SQL/ pandas 操作 |

### 2.3 分析模板类型

每个模板对应一个固定的渲染布局，AI 只负责选择模板和填充数据：

| 模板名 | 适用问题 | 渲染内容 |
|--------|---------|---------|
| `person_timesheet` | 某人某时段报工 | 趋势折线图 + 工单明细表 + 汇总卡 |
| `team_overview` | 团队/工种整体情况 | KPI 卡片 + 人员排行 + 柱状图 |
| `order_progress` | 工单进度分析 | 甘特图 + 风险标记 + 工时对比 |
| `material_shortage` | 缺料分析 | 缺料清单 + 影响工单 + 承诺日期 |
| `efficiency_analysis` | 效率分析 | 实际 vs 标准工时 + 效率排名 |
| `causal_chain` | 归因分析 | 因果链图 + 关键事件时间线 |
| `data_table` | 通用列表查询 | 可筛选数据表 |
| `summary_card` | 简单汇总 | 多个 metric 卡片 |

---

## 3. 分阶段实施计划

### Phase 1: Copilot Hub 基础框架（第 1 周）

**目标**: 把 `pages/16_智能助理.py` 改造成主入口，支持输入框 + 动态页签。

#### Task 1.1: 创建页签管理器

**文件**:  
- 创建: `core/agent/tab_manager.py`

**步骤**:
- [ ] 定义 `Tab` 数据类：`id`、`title`、`template`、`data`、`created_at`
- [ ] 实现 `create_tab()`：创建新页签
- [ ] 实现 `close_tab()`：关闭页签
- [ ] 实现 `switch_tab()`：切换当前页签
- [ ] 实现 `update_tab()`：更新页签内容（多轮对话）
- [ ] 实现 `get_tabs()` / `get_active_tab()`：读取状态
- [ ] 使用 `st.session_state` 持久化页签列表

**验证**:
- [ ] 单元测试：创建、关闭、切换页签正常
- [ ] 在临时页面中可渲染页签 UI

#### Task 1.2: 重构 Copilot Hub 页面

**文件**:  
- 修改: `pages/16_智能助理.py`

**步骤**:
- [ ] 页面标题改为"🤖 工厂 Copilot 中心"
- [ ] 顶部放置大输入框（类似 ChatGPT 首页）
- [ ] 输入框下方显示建议问题（可点击）
- [ ] 中部渲染页签栏（类似浏览器标签）
- [ ] 页签内容区默认显示欢迎语 + 能力说明
- [ ] 支持点击页签切换、点击 x 关闭
- [ ] 用户输入后，生成新页签并切换到该页签

**验证**:
- [ ] 输入问题后生成新页签
- [ ] 可切换/关闭页签
- [ ] 无异常报错

#### Task 1.3: 把现有快速查询接入新 Hub

**文件**:  
- 修改: `core/agent/copilot_widget.py`
- 修改: `core/agent/intent_router.py`

**步骤**:
- [ ] 把 `_handle_query()` 的快速查询逻辑迁移/复用到 Hub
- [ ] 简单查询（某人报工、总工时、缺料）直接生成 `summary_card` 或 `data_table` 页签
- [ ] 保留底部 Copilot widget 在其他页面的嵌入

**验证**:
- [ ] "张三今天报工多少" → 生成结果页签，秒回
- [ ] "今天有哪些缺料" → 生成缺料列表页签

---

### Phase 2: 分析模板体系（第 2 周）

**目标**: 建立模板化渲染机制，让 AI 能生成结构化分析界面。

#### Task 2.1: 定义模板数据规范

**文件**:  
- 创建: `core/agent/templates/__init__.py`
- 创建: `core/agent/templates/base.py`

**步骤**:
- [ ] 定义 `AnalysisTemplate` 基类
- [ ] 每个模板实现 `render(data)` 方法
- [ ] 定义模板输入数据 schema（用 dataclass 或 TypedDict）
- [ ] 定义模板选择器接口

**验证**:
- [ ] 至少实现 3 个基础模板：summary_card、data_table、person_timesheet
- [ ] 每个模板可独立渲染

#### Task 2.2: 实现核心分析模板

**文件**:  
- 创建: `core/agent/templates/person_timesheet.py`
- 创建: `core/agent/templates/team_overview.py`
- 创建: `core/agent/templates/order_progress.py`
- 创建: `core/agent/templates/material_shortage.py`
- 创建: `core/agent/templates/efficiency_analysis.py`

**步骤**:
- [ ] `person_timesheet`：按日期趋势 + 按工单 breakdown + 总工时
- [ ] `team_overview`：KPI 卡片 + 人员排行 + 工种分布
- [ ] `order_progress`：工单甘特图 + 实际/标准工时对比
- [ ] `material_shortage`：缺料清单 + 影响工单
- [ ] `efficiency_analysis`：效率排行 + 实际 vs 标准

**验证**:
- [ ] 用模拟数据渲染每个模板
- [ ] 模板在页签中显示正常

#### Task 2.3: 创建视图渲染器

**文件**:  
- 创建: `core/agent/view_renderer.py`

**步骤**:
- [ ] 实现 `render_tab(tab)`：根据 tab.template 分发到对应模板
- [ ] 实现 `template_registry`：模板名 → 模板类
- [ ] 统一处理模板异常（数据缺失、格式错误）
- [ ] 支持模板内的"切换视图"（如表格 ↔ 图表）

**验证**:
- [ ] 给定不同 template 名，渲染对应模板
- [ ] 数据异常时显示友好提示

#### Task 2.4: 扩展意图识别支持分析类型

**文件**:  
- 修改: `core/agent/intent_router.py`

**步骤**:
- [ ] 在 query 意图下增加 `分析类型` 字段
- [ ] 规则匹配常见分析类型：
  - 趋势分析："趋势""走势""变化"
  - 对比分析："对比""排名""最多""最少"
  - 归因分析："为什么""原因""延期"
  - 列表查询："有哪些""列表""明细"
- [ ] 复杂意图仍走 LLM 识别

**验证**:
- [ ] "张三本周报工趋势" → 分析类型=trend
- [ ] "本周谁加班最多" → 分析类型=rank
- [ ] "WO-001 为什么延期" → 分析类型=causal

---

### Phase 3: 数据查询与分析引擎（第 3 周上半）

**目标**: 让 Copilot 能自动从数据库取数并进行基础分析。

#### Task 3.1: 构建查询构造器

**文件**:  
- 创建: `core/agent/query_builder.py`

**步骤**:
- [ ] 实现 `build_person_query(employee, start, end)`：查询某人工时
- [ ] 实现 `build_team_query(trade, start, end)`：查询团队工时
- [ ] 实现 `build_order_query(order_id)`：查询工单进度
- [ ] 实现 `build_shortage_query(start, end)`：查询缺料
- [ ] 实现 `build_efficiency_query(start, end)`：查询效率
- [ ] 每个函数返回 SQL + 参数

**验证**:
- [ ] 各查询在 PostgreSQL 上执行正确
- [ ] 单元测试覆盖主要查询

#### Task 3.2: 实现数据分析函数

**文件**:  
- 创建: `core/agent/analytics.py`

**步骤**:
- [ ] 实现 `analyze_person_timesheet(rows)`：汇总、趋势、按工单分组
- [ ] 实现 `analyze_team_overview(rows)`：总工时、人均、排名
- [ ] 实现 `analyze_order_progress(rows)`：进度百分比、偏差率
- [ ] 实现 `analyze_efficiency(rows)`：效率、排名、超标标记
- [ ] 实现 `analyze_shortage_impact(rows)`：缺料影响工单数

**验证**:
- [ ] 输入模拟数据，输出符合模板要求的数据结构

#### Task 3.3: 连接意图 → 查询 → 模板

**文件**:  
- 修改: `core/agent/copilot_widget.py` 或新建 `core/agent/hub_controller.py`

**步骤**:
- [ ] 创建 `handle_analysis(intent, user_input)` 主流程
- [ ] 根据意图中的对象、时间范围、分析类型，选择查询构造器
- [ ] 执行查询，调用 analytics 函数分析
- [ ] 选择合适模板，生成 tab
- [ ] 在 tab 中保留原始查询条件，支持"只看钳工"等二次筛选

**验证**:
- [ ] "张三本周报工" → 查询 → 分析 → 渲染 person_timesheet 模板
- [ ] "今天总工时" → 查询 → 渲染 summary_card 模板

---

### Phase 4: 现有页面 Copilot 化（第 3 周下半 ~ 第 4 周上半）

**目标**: 把现有 21 个页面的核心能力变成 Copilot 可调用的"视图"，逐步减少用户对固定菜单的依赖。

#### Task 4.1: 提取各页面核心数据查询

**文件**:  
- 修改: 各 `pages/*.py`

**步骤**:
- [ ] 把每个页面的数据加载逻辑封装为 `get_xxx_data()` 函数
- [ ] 把数据查询从 Streamlit UI 代码中分离
- [ ] 确保这些函数可被 `core/agent/` 调用

**优先提取的页面**:
- `4_人员维度.py` → `get_person_dimension_data()`
- `3_设备维度.py` → `get_equipment_dimension_data()`
- `5_工单进度.py` → `get_order_progress_data()`
- `6_效率看板.py` → `get_efficiency_data()`
- `8_缺料跟踪.py` → `get_shortage_data()`

**验证**:
- [ ] 页面本身仍能正常加载
- [ ] Copilot 可通过函数获取同样数据

#### Task 4.2: 把固定视图注册为 Copilot 可召唤视图

**文件**:  
- 创建: `core/agent/view_registry.py`

**步骤**:
- [ ] 定义"视图"元数据：名称、描述、所需参数、数据函数、推荐模板
- [ ] 注册各页面核心视图为 Copilot 可用视图
- [ ] 用户说"打开人员维度"时，生成对应页签而不是跳转页面

**验证**:
- [ ] "打开人员维度" → 生成人员维度页签
- [ ] 页签内容和原页面一致

#### Task 4.3: 复杂查询接入 ReAct

**文件**:  
- 修改: `core/agent/react_agent.py`
- 修改: `core/agent/prompts.py`

**步骤**:
- [ ] 扩展 ReAct prompt，让 LLM 知道可以生成分析页签
- [ ] LLM 可以调用"生成分析页签"工具，传入 template + data
- [ ] 为复杂问题（如"为什么延期"）定义分析 workflow
- [ ] 多步分析结果汇总到一个 tab

**验证**:
- [ ] "WO-001 为什么延期" → 走 ReAct → 生成 causal_chain 页签
- [ ] 多步分析结果可在页签内查看

---

### Phase 5: 导航重构与页面精简（第 4 周下半）

**目标**: 减少固定页面数量，让 Copilot Hub 成为默认首页。

#### Task 5.1: 把 Copilot Hub 设为默认首页

**文件**:  
- 修改: `app.py`

**步骤**:
- [ ] 侧边栏第一个入口改为"🤖 Copilot 中心"
- [ ] 点击 logo/标题返回 Copilot Hub
- [ ] 保留"全部功能"入口作为过渡

**验证**:
- [ ] 打开 `http://localhost:8501` 默认进入 Copilot Hub
- [ ] 侧边栏入口顺序正确

#### Task 5.2: 合并/精简固定页面

**合并策略**:

| 当前页面 | 合并后 | 说明 |
|---------|--------|------|
| `0_项目报工.py` + `1_组长报工.py` | `报工录入` | 统一报工入口 |
| `2_今日总览.py` + `3_设备维度.py` + `4_人员维度.py` + `6_效率看板.py` | `数据看板` | 统一分析视图入口 |
| `5_工单进度.py` + `8_缺料跟踪.py` + `10_BOM展开.py` | `工单中心` | 统一工单相关 |
| `9_系统配置.py` | 保留 | 配置类操作仍需固定界面 |
| `15_数据同步.py` | 保留 | 同步操作需要明确入口 |

**步骤**:
- [ ] 创建合并后的新页面（或直接在 Copilot Hub 中提供入口）
- [ ] 原有页面保留但降级到"全部功能"菜单
- [ ] 在 Copilot Hub 中，用户说"去报工"时打开合并后的报工页

**验证**:
- [ ] 合并后页面功能完整
- [ ] Copilot 能正确跳转

#### Task 5.3: 添加"全部功能"抽屉

**文件**:  
- 修改: `pages/16_智能助理.py`

**步骤**:
- [ ] 在 Hub 页面添加"全部功能"展开按钮
- [ ] 列出仍需固定页面的功能入口
- [ ] 为新用户提供过渡期的安全感

**验证**:
- [ ] "全部功能"可展开
- [ ] 点击可进入对应页面

---

### Phase 6: 高级能力（可选，第 5 周及以后）

#### Task 6.1: 多轮对话与页签内二次分析

**步骤**:
- [ ] 在页签内显示"继续问"输入框
- [ ] 支持"只看钳工""换成折线图""导出 Excel"等二次指令
- [ ] 上下文传递给 LLM，保持分析连续性

#### Task 6.2: 页签协作与对比

**步骤**:
- [ ] 支持选择两个页签做对比
- [ ] 生成对比分析页签
- [ ] 支持页签分组（如"本周分析""人员分析"）

#### Task 6.3: 自然语言录入

**步骤**:
- [ ] 支持"给张三报 8 小时到 WO-001"
- [ ] 系统在页签内显示待确认表单
- [ ] 用户确认后写入数据库

---

## 4. 技术实现要点

### 4.1 页签状态管理

使用 `st.session_state` 存储页签：

```python
st.session_state["copilot_tabs"] = [
    {"id": "tab_1", "title": "张三本周报工", "template": "person_timesheet", "data": {...}},
    {"id": "tab_2", "title": "今天总工时", "template": "summary_card", "data": {...}},
]
st.session_state["copilot_active_tab"] = "tab_2"
```

### 4.2 模板渲染规范

每个模板接收统一数据结构：

```python
{
    "title": "页签标题",
    "summary": {"总工时": 40.5, "工单数": 5},
    "chart": {"type": "line", "data": [...]},
    "table": {"columns": [...], "data": [...]},
    "context": {"employee": "张三", "start": "2026-06-16", "end": "2026-06-22"}
}
```

### 4.3 意图到模板的映射

```
对象=人 + 指标=报工/工时 + 分析类型=trend → person_timesheet
对象=空 + 指标=总工时 → summary_card
对象=工单 + 分析类型=progress → order_progress
对象=空 + 指标=缺料 → material_shortage
分析类型=rank → team_overview / efficiency_analysis
分析类型=causal → causal_chain
```

### 4.4 与现有能力的衔接

- **数据库查询**: 复用 `core/db.py` + `core/database.py`
- **LLM 调用**: 复用 `core/agent/llm_client.py`
- **工具调用**: 复用 `core/agent/tool_registry.py`
- **页面跳转**: 复用 `st.switch_page()`
- **权限控制**: 复用 `core/auth.py`

---

## 5. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| AI 输出不稳定 | 用户体验差 | 模板化渲染，AI 只选模板填数据 |
| LLM 调用慢 | 复杂查询等待久 | 简单查询走规则快速路径；复杂查询显示进度 |
| 用户不习惯 | 抵触新交互 | 保留"全部功能"抽屉；首页提供示例问题 |
| 现有功能遗漏 | 改造中破坏功能 | 每个页面改造后完整测试；保留原页面备份 |
| 数据权限问题 | AI 越权查询 | 在查询层统一做权限过滤 |
| 页签过多混乱 | 界面拥挤 | 支持关闭、分组、最多显示 8 个页签 |

---

## 6. 检查计划（验收标准）

### 6.1 每阶段交付检查

#### Phase 1 检查项
- [ ] `core/agent/tab_manager.py` 存在且单测通过
- [ ] 打开 `pages/16_智能助理.py` 显示输入框 + 页签区
- [ ] 输入"张三今天报工多少"后生成新页签并秒回
- [ ] 可正常切换/关闭页签

#### Phase 2 检查项
- [ ] 至少 5 个分析模板已实现
- [ ] `core/agent/view_renderer.py` 能根据模板名正确渲染
- [ ] 意图路由器能识别 trend/rank/causal/list 等分析类型
- [ ] 模板在页签中显示正常

#### Phase 3 检查项
- [ ] `core/agent/query_builder.py` 覆盖主要查询场景
- [ ] `core/agent/analytics.py` 能输出模板所需数据结构
- [ ] 从意图 → 查询 → 分析 → 模板渲染的完整链路跑通
- [ ] 至少 3 类问题能自动生成分析页签

#### Phase 4 检查项
- [ ] 至少 5 个核心页面的数据函数被提取
- [ ] "打开人员维度"等指令生成对应页签
- [ ] 复杂问题（如"为什么延期"）走 ReAct 生成分析页签

#### Phase 5 检查项
- [ ] `app.py` 默认进入 Copilot Hub
- [ ] 固定页面数量从 21 个减少到 10 个以内
- [ ] "全部功能"抽屉可用
- [ ] 所有原有功能仍可通过某种方式访问

### 6.2 最终验收检查

#### 功能验收
- [ ] 用户打开系统，主界面是 Copilot Hub
- [ ] 高频查询（人员报工、总工时、缺料、工单进度、效率）都能通过自然语言生成页签
- [ ] 复杂查询（归因、对比）走 ReAct 后生成分析页签
- [ ] 页签支持切换、关闭、二次分析
- [ ] 数据录入仍可通过固定页面或自然语言完成

#### 性能验收
- [ ] 简单查询响应时间 < 2 秒
- [ ] 复杂查询有明确进度提示
- [ ] 打开 Copilot Hub 时间 < 3 秒

#### 兼容性验收
- [ ] 21 个原有页面至少 80% 的功能仍然可用
- [ ] 所有单元测试通过
- [ ] 数据库 schema 无需大改

#### 用户体验验收
- [ ] 首页提供示例问题
- [ ] "全部功能"入口可见
- [ ] 页签标题清晰反映内容
- [ ] 空数据/错误状态有友好提示

### 6.3 我检查时会重点看

等你改完后，我会从这几个维度检查：

1. **代码层面**
   - `core/agent/` 下新增了哪些模块，职责是否清晰
   - `pages/16_智能助理.py` 是否已经成为主入口
   - 模板、渲染器、页签管理器是否解耦

2. **运行层面**
   - 打开 `http://localhost:8501` 是否默认进入 Hub
   - 输入常见问题是否能秒回
   - 页签交互是否流畅

3. **测试层面**
   - `pytest tests/` 是否全部通过
   - 新增模块是否有单元测试
   - AppTest 测试 21 个页面是否仍通过（或更新后的页面通过）

4. **文档层面**
   - 改造后的使用说明是否更新
   - 新增模板的使用方式是否有文档

---

## 7. 建议的启动方式

如果你想最小成本验证这个方向，建议先做 **Phase 1 + Phase 2 的前两个 Task**：

1. 把 `pages/16_智能助理.py` 改成输入框 + 页签
2. 实现 3 个模板：summary_card、data_table、person_timesheet
3. 把现有快速查询接入

这样 3-5 天就能出一个可体验的 Demo。等验证方向正确后，再按 Phase 3-5 推进。

---

## 8. 相关文件清单

### 新增文件
- `core/agent/tab_manager.py`
- `core/agent/view_renderer.py`
- `core/agent/query_builder.py`
- `core/agent/analytics.py`
- `core/agent/view_registry.py`
- `core/agent/templates/__init__.py`
- `core/agent/templates/base.py`
- `core/agent/templates/person_timesheet.py`
- `core/agent/templates/team_overview.py`
- `core/agent/templates/order_progress.py`
- `core/agent/templates/material_shortage.py`
- `core/agent/templates/efficiency_analysis.py`
- `core/agent/templates/causal_chain.py`
- `tests/test_agent/test_tab_manager.py`
- `tests/test_agent/test_templates.py`
- `tests/test_agent/test_query_builder.py`
- `tests/test_agent/test_analytics.py`

### 修改文件
- `pages/16_智能助理.py`（重写为主入口）
- `app.py`（默认首页）
- `core/agent/intent_router.py`（扩展分析意图）
- `core/agent/copilot_widget.py`（提取快速查询逻辑）
- `core/agent/react_agent.py`（支持生成页签）
- `core/agent/prompts.py`（扩展 ReAct prompt）
- 各 `pages/*.py`（提取数据函数）

### 可选删除/合并
- 合并后的旧页面可删除或归档到 `pages/archive/`

---

**下一步**: 你可以按这个计划开始改造。完成一个 Phase 后告诉我，我先检查这一阶段；也可以全部做完后统一检查。
