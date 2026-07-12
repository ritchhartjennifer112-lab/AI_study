# 工厂工时管理系统 — 统一设计方案

> 简奢 · 工业美感 · 全系统统一

---

## 一、设计方向

### 调性定义

**简奢工业（Industrial Refinement）**

不是"炫酷的深色 SaaS 仪表盘"，也不是"冰冷的工厂控制台"。
是**高端精密仪器的操作界面** — 像瑞士钟表工坊的数字终端，或保时捷车内的触控屏。

核心关键词：**克制、精密、可信、高效**

- 克制 — 每个元素都有存在的理由，没有装饰性元素
- 精密 — 间距精确到像素级节奏，对齐严谨
- 可信 — 深色不是为了"酷"，是为了车间强光下可读
- 高效 — 信息密度高但不拥挤，一眼看到关键数据

### 用户记忆锚点

> "这个系统看起来像**专业设备的操作界面**，不像一个网页应用。"

---

## 二、色彩系统

### 主色板（OKLCH 定义，CSS 变量输出）

```css
:root {
  /* ── 表面层 ── */
  --surface-base:     oklch(0.145 0.012 250);    /* #0c1220  深碳黑，主背景 */
  --surface-raised:   oklch(0.175 0.010 250);    /* #111a2b  卡片/面板背景 */
  --surface-overlay:  oklch(0.210 0.009 250);    /* #172033  弹出层/hover */
  --surface-muted:    oklch(0.240 0.008 250);    /* #1c2740  分隔/次级区域 */

  /* ── 边框 ── */
  --border-subtle:    oklch(0.280 0.008 250);    /* #243050  微妙分隔 */
  --border-default:   oklch(0.320 0.008 250);    /* #2d3a58  标准边框 */
  --border-strong:    oklch(0.380 0.008 250);    /* #3a4a6e  强调边框 */

  /* ── 文字 ── */
  --text-primary:     oklch(0.930 0.006 250);    /* #e8ecf4  主文字 */
  --text-secondary:   oklch(0.680 0.008 250);    /* #8899b3  次要文字 */
  --text-muted:       oklch(0.520 0.008 250);    /* #5e6e8a  辅助说明 */

  /* ── 功能色 ── */
  --accent-blue:      oklch(0.650 0.145 255);    /* #3b82f6  主操作/链接 */
  --accent-blue-dim:  oklch(0.650 0.145 255) / 0.15;  /* 蓝色透明底 */
  --accent-green:     oklch(0.720 0.170 155);    /* #10b981  成功/在线/正常 */
  --accent-amber:     oklch(0.780 0.155 75);     /* #f59e0b  警告/注意 */
  --accent-red:       oklch(0.650 0.200 25);     /* #ef4444  错误/危险/逾期 */
  --accent-cyan:      oklch(0.750 0.120 195);    /* #06b6d4  信息/辅助 */

  /* ── 金属色（装饰性强调）── */
  --metal-gold:       oklch(0.780 0.120 85);     /* 铜金色，仅用于标题装饰线 */
  --metal-steel:      oklch(0.550 0.015 250);    /* 钢灰色，次要装饰 */
}
```

### 色彩使用规则

| 场景 | 用色 | 禁止 |
|---|---|---|
| 主背景 | `surface-base` | 不用纯黑 `#000` |
| 卡片/面板 | `surface-raised` | 不用 `surface-base` 同色（无层次） |
| 主操作按钮 | `accent-blue` 实底 | 不用渐变 |
| 成功状态 | `accent-green` | — |
| 警告状态 | `accent-amber` | — |
| 危险状态 | `accent-red` | — |
| 标题文字 | `text-primary` | 不用纯白 `#fff` |
| 说明文字 | `text-secondary` 或 `text-muted` | 不用 `#999` |
| 装饰线条 | `metal-gold`，≤1px，仅标题下方 | 不用大面积金色 |

---

## 三、字体系统

### 字体选择

```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;600;700&display=swap');

:root {
  --font-sans:    'DM Sans', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'Cascadia Code', monospace;
}
```

**选择理由**：
- **DM Sans** — 几何无衬线，比 Inter 更有精密感，字怀更开放，工业仪表风格
- **JetBrains Mono** — 数据/代码展示，等宽对齐，精密仪器感
- **Noto Sans SC** — 中文 fallback，与 DM Sans 几何风格匹配

### 字号层级

| 层级 | 用途 | 字号 | 字重 | 行高 |
|---|---|---|---|---|
| Display | 页面大标题（极少用） | clamp(1.5rem, 3vw, 2rem) | 700 | 1.2 |
| H1 | 页面标题 | 1.5rem (24px) | 600 | 1.3 |
| H2 | 区块标题 | 1.125rem (18px) | 600 | 1.4 |
| H3 | 子标题 | 1rem (16px) | 500 | 1.4 |
| Body | 正文 | 0.875rem (14px) | 400 | 1.6 |
| Caption | 辅助说明 | 0.75rem (12px) | 400 | 1.5 |
| KPI | 大数字 | clamp(1.75rem, 4vw, 2.5rem) | 700 | 1.1 |
| Mono | 数据/代码 | 0.8125rem (13px) | 400 | 1.5 |

---

## 四、间距与栅格

### 间距体系（4px 基数）

| Token | 值 | 用途 |
|---|---|---|
| `--space-1` | 4px | 图标与文字间距 |
| `--space-2` | 8px | 紧凑元素内间距 |
| `--space-3` | 12px | 按钮内间距、小卡片 |
| `--space-4` | 16px | 标准内间距 |
| `--space-5` | 20px | 卡片内间距 |
| `--space-6` | 24px | 区块间距 |
| `--space-8` | 32px | 大区块间距 |
| `--space-10` | 40px | 页面顶部留白 |
| `--space-12` | 48px | 页面级间距 |

### 圆角

| Token | 值 | 用途 |
|---|---|---|
| `--radius-sm` | 4px | 小元素（badge、tag） |
| `--radius-md` | 8px | 按钮、输入框 |
| `--radius-lg` | 12px | 卡片、面板 |
| `--radius-xl` | 16px | 弹窗、大面板 |

**原则**：圆角偏小，保持精密感。不用 20px+ 的大圆角（那是消费级产品的做法）。

---

## 五、组件规范

### 5.1 按钮

```
Primary:   蓝色实底，白色文字，hover 变深
Secondary: 透明底 + 边框，文字色
Ghost:     无边框，文字色，hover 显示微妙背景
Danger:    红色实底（仅删除/危险操作）
```

- 最小高度：40px（车间触控建议 48px）
- 内间距：`12px 20px`
- 字号：14px，字重 500
- 过渡：`all 0.15s ease-out`

### 5.2 输入框

```
背景: surface-overlay
边框: border-default，1px
聚焦: accent-blue 边框 + 2px glow
圆角: 8px
高度: 40px（触控场景 48px）
```

### 5.3 卡片 / 面板

```
背景: surface-raised
边框: border-subtle，1px
圆角: 12px
内间距: 20px
阴影: 无（不拟态）
```

**禁止**：嵌套卡片、玻璃拟态、渐变背景。

### 5.4 标签页（Tabs）

```
选中态: 底部 2px accent-blue 实线
未选中: 文字 text-muted，无边框
间距: 标签间 24px
```

### 5.5 数据表格

```
表头: surface-muted 背景，text-secondary 文字，字重 600
行: 交替 surface-base / surface-raised（斑马纹）
行高: 48px（触控友好）
hover: surface-overlay
边框: 仅底部 border-subtle
```

### 5.6 KPI 卡片

```
布局: 数字(大) + 标签(小) + 趋势指示器
数字: --font-mono, KPI 字号, text-primary
标签: --font-sans, Caption 字号, text-muted
趋势: accent-green(↑) / accent-red(↓) / text-muted(→)
背景: surface-raised，无装饰
```

### 5.7 状态指示器

```
在线/正常:  6px 圆点，accent-green
警告:      6px 圆点，accent-amber
危险/逾期:  6px 圆点，accent-red
离线/停用:  6px 圆点，text-muted
```

---

## 六、对话框（Copilot Widget）设计

这是全系统最重要的组件 — 所有用户的唯一入口。

### 设计原则

- **不是"网页底部聊天框"**，是"精密仪器的命令终端"
- 暗色背景融入整体主题，不是白色浮层
- 对话气泡克制，不花哨

### 具体规范

```
容器:
  背景: surface-raised（与页面同色系，微抬升）
  顶部边框: 1px border-subtle
  位置: fixed bottom, 全宽
  内间距: 16px 24px

用户消息气泡:
  背景: accent-blue（主色，实底）
  文字: white
  圆角: 12px 12px 4px 12px（右下角收紧）
  最大宽度: 70%
  对齐: 右侧

助手消息气泡:
  背景: surface-overlay
  文字: text-primary
  圆角: 12px 12px 12px 4px（左下角收紧）
  最大宽度: 80%
  对齐: 左侧

输入框:
  背景: surface-base
  边框: border-default
  圆角: 8px
  占位符文字: text-muted
  图标: 左侧小飞机图标，accent-blue
```

### 对话中跳转的视觉处理

当 Agent 执行页面跳转时，在对话中显示一个**跳转卡片**：

```
┌─────────────────────────────────────┐
│  📊 已打开「设备维度」看板            │
│                                     │
│  [查看设备维度]                      │ ← 蓝色链接按钮
│                                     │
│  你可以继续在这里提问，              │
│  或直接操作看板上的筛选器。          │
└─────────────────────────────────────┘

样式:
  背景: surface-muted
  边框-left: 3px accent-blue（左侧蓝色指示条）
  圆角: 8px
  内间距: 12px 16px
```

---

## 七、页面布局模板

### 7.1 标准分析页（设备维度/人员维度/工单进度等）

```
┌─────────────────────────────────────────────────┐
│  页面标题                          [筛选器区域]   │  ← 顶部：标题 + 操作
│  ─────────────────────────────────────────────── │  ← 1px 分隔线 metal-gold
│                                                 │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐            │  ← KPI 行：4 个指标卡
│  │ KPI │  │ KPI │  │ KPI │  │ KPI │            │
│  └─────┘  └─────┘  └─────┘  └─────┘            │
│                                                 │
│  ┌───────────────────────┐ ┌─────────────────┐  │  ← 主内容：左图表 + 右表格
│  │                       │ │                 │  │
│  │      图表区域          │ │    数据表格      │  │
│  │                       │ │                 │  │
│  └───────────────────────┘ └─────────────────┘  │
│                                                 │
│  ─── Copilot 对话框 ─────────────────────────── │  ← 底部对话框
└─────────────────────────────────────────────────┘
```

### 7.2 报工页（组长报工/项目报工）

```
┌─────────────────────────────────────────────────┐
│  报工表单                                        │
│  ─────────────────────────────────────────────── │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  员工: [下拉选择]     工单: [下拉选择]    │    │  ← 表单区：两列布局
│  │  工时: [数字输入]     状态: [单选]        │    │
│  │  备注: [文本输入________________]         │    │
│  │                          [提交报工]       │    │  ← 主操作按钮
│  └─────────────────────────────────────────┘    │
│                                                 │
│  今日已报工:                                     │
│  ┌─────────────────────────────────────────┐    │
│  │  数据表格（今日汇总）                     │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ─── Copilot 对话框 ─────────────────────────── │
└─────────────────────────────────────────────────┘
```

### 7.3 智能助理首页（16_智能助理）

```
┌─────────────────────────────────────────────────┐
│                                                 │
│                                                 │
│         ┌───────────────────────────┐           │
│         │      工厂智能助理          │           │  ← 居中欢迎区
│         │                           │           │
│         │  你好，管理员。            │           │
│         │  今天想了解什么？          │           │
│         │                           │           │
│         │  ┌─────┐ ┌─────┐ ┌─────┐ │           │  ← 快捷操作卡片
│         │  │今日  │ │工单  │ │缺料  │ │           │
│         │  │总览  │ │进度  │ │跟踪 │ │           │
│         │  └─────┘ └─────┘ └─────┘ │           │
│         │                           │           │
│         │  ┌─────┐ ┌─────┐ ┌─────┐ │           │
│         │  │效率  │ │人员  │ │派工  │ │           │
│         │  │分析  │ │到位  │ │建议 │ │           │
│         │  └─────┘ └─────┘ └─────┘ │           │
│         │                           │           │
│         └───────────────────────────┘           │
│                                                 │
│  ─── Copilot 对话框 ─────────────────────────── │
└─────────────────────────────────────────────────┘
```

---

## 八、CSS 实现方案

### 8.1 config.toml 更新

```toml
[theme]
primaryColor = "#3b82f6"
backgroundColor = "#0c1220"
secondaryBackgroundColor = "#111a2b"
textColor = "#e8ecf4"
font = "sans serif"

[server]
headless = true
```

### 8.2 auth.py apply_global_theme() 更新

将当前的 CSS 变量替换为新色板，主要改动：

```css
:root {
  /* 替换旧变量为新色板 */
  --surface-base:     #0c1220;
  --surface-raised:   #111a2b;
  --surface-overlay:  #172033;
  --surface-muted:    #1c2740;

  --border-subtle:    #243050;
  --border-default:   #2d3a58;
  --border-strong:    #3a4a6e;

  --text-primary:     #e8ecf4;
  --text-secondary:   #8899b3;
  --text-muted:       #5e6e8a;

  --accent-blue:      #3b82f6;
  --accent-green:     #10b981;
  --accent-amber:     #f59e0b;
  --accent-red:       #ef4444;
  --accent-cyan:      #06b6d4;

  --metal-gold:       #c9a84c;

  --font-sans:  'DM Sans', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono:  'JetBrains Mono', 'Cascadia Code', monospace;
}
```

新增组件级样式：标签页、表格、KPI 卡片、状态指示器等。

### 8.3 copilot_widget.py CSS 更新

将白色背景替换为融入主题的暗色设计：

```css
.copilot-container {
  background: var(--surface-raised);
  border-top: 1px solid var(--border-subtle);
  box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
}
```

消息气泡、输入框等全部使用 CSS 变量。

---

## 九、实施路径

| 步骤 | 文件 | 改动内容 |
|---|---|---|
| **1** | `.streamlit/config.toml` | 更新主题色为暗色 |
| **2** | `core/auth.py` | 重写 `apply_global_theme()` CSS，使用新色板 + 字体 + 组件样式 |
| **3** | `core/agent/copilot_widget.py` | 重写 `COPILOT_CSS`，暗色对话框 + 消息气泡 + 跳转卡片 |
| **4** | `app.py` | 首页跳转逻辑不变，确认全局主题正确加载 |
| **5** | 各页面文件 | 移除页面内重复的 CSS（统一由 auth.py 管理） |

**总改动量**：3 个核心文件重写 CSS + 约 20 个页面清理冗余样式。

---

## 十、设计禁忌清单

| 禁止 | 原因 |
|---|---|
| 紫色渐变 / 蓝紫渐变 | AI 通病，毫无辨识度 |
| 玻璃拟态 (glassmorphism) | 车间强光下不可读 |
| 纯白 / 纯黑背景 | 不自然，对比度太极端 |
| bounce / elastic 动画 | 过时，不精密 |
| 卡片嵌套卡片 | 信息层级混乱 |
| 侧边条纹装饰 | 无意义装饰 |
| 大数字 + 小标签 + 渐变底 | SaaS 模板套路 |
| Inter / Roboto / Arial | 无辨识度 |
| 所有 section 加 `01/02/03` 编号 | AI 语法 |
| 每个区块上方小号大写副标题 | AI 语法 |
