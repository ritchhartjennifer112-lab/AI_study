# Factory OS Phase 0: Design System + 项目脚手架

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 本文件包含 Phase 0 的 12 个 Task。每个 Task 由独立 subagent 执行，先读本文件完整内容再开始。

---

## 环境准备

### 第一步：删除 Streamlit 文件（进入 Phase 0 时一次性完成）

```bash
cd d:/AI知识库/AI++++/工厂现场——工时

# Streamlit 页面（21 个文件）
rm -f app.py
rm -f pages/0_项目报工.py pages/1_组长报工.py pages/2_今日总览.py
rm -f pages/3_设备维度.py pages/4_人员维度.py pages/5_工单进度.py
rm -f pages/6_效率看板.py pages/7_标准工时健康度.py pages/8_缺料跟踪.py
rm -f pages/9_系统配置.py pages/10_BOM展开.py pages/11_人员看板.py
rm -f pages/12_因果分析.py pages/13_来源追溯.py pages/14_本体视图.py
rm -f pages/15_数据同步.py pages/16_智能助理.py pages/17_生产计划.py
rm -f pages/18_派工建议.py pages/20_收件箱管理.py pages/21_在职人员清单.py

# Streamlit 认证 + Copilot + 配置
rm -f core/auth.py
rm -f core/agent/copilot_widget.py
rm -f .streamlit/config.toml

# 旧设计文件
rm -f docs/design-preview*.html

git add -A && git commit -m "feat: Phase 0 — 删除全部 Streamlit 文件，准备重构"
```

### 第二步：初始化 Next.js 项目

```bash
cd d:/AI知识库/AI++++/工厂现场——工时
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
```

上述命令会创建 `frontend/` 目录并安装所有依赖。

安装额外依赖：
```bash
cd frontend
npx shadcn@latest init -d --force
npx shadcn@latest add button card input select table badge separator tabs sheet command dialog toast

npm install recharts @tanstack/react-table lucide-react clsx tailwind-merge class-variance-authority
```

---

### 设计系统变量（直接写入 globals.css，在整个 Phase 0 中统一使用）

以下 CSS 变量来自 `docs/design-system.md`，所有组件基于此变量体系：

```css
/* frontend/src/app/globals.css — 完整内容 */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* 表面层 */
  --surface-base: oklch(0.145 0.012 250);
  --surface-raised: oklch(0.175 0.010 250);
  --surface-overlay: oklch(0.210 0.009 250);
  --surface-muted: oklch(0.240 0.008 250);

  /* 边框 */
  --border-subtle: oklch(0.280 0.008 250);
  --border-default: oklch(0.320 0.008 250);
  --border-strong: oklch(0.380 0.008 250);

  /* 文字 */
  --text-primary: oklch(0.930 0.006 250);
  --text-secondary: oklch(0.680 0.008 250);
  --text-muted: oklch(0.520 0.008 250);

  /* 功能色 */
  --accent-blue: oklch(0.650 0.145 255);
  --accent-green: oklch(0.720 0.170 155);
  --accent-amber: oklch(0.780 0.155 75);
  --accent-red: oklch(0.650 0.200 25);
  --accent-cyan: oklch(0.750 0.120 195);

  /* 字体 */
  --font-sans: 'DM Sans', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Cascadia Code', monospace;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-family: var(--font-sans);
  color: var(--text-primary);
  background: var(--surface-base);
}

body {
  min-height: 100vh;
  background: var(--surface-base);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.6;
}

/* 滚动条 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-strong); }
```

---

## Task 0-1: AppShell + Sidebar + TopBar 布局组件

**文件：**
- Create: `frontend/src/components/app-shell.tsx`
- Create: `frontend/src/components/sidebar.tsx`
- Create: `frontend/src/components/topbar.tsx`

### Step 1: 创建 Sidebar

```tsx
// frontend/src/components/sidebar.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Factory,
  Wrench,
  Users,
  Package,
  Database,
  Settings,
  Terminal,
} from 'lucide-react';

const navItems = [
  { href: '/', label: '指挥中心', icon: LayoutDashboard },
  { href: '/production', label: '生产中心', icon: Factory },
  { href: '/equipment', label: '设备中心', icon: Wrench },
  { href: '/personnel', label: '人员中心', icon: Users },
  { href: '/materials', label: '物料中心', icon: Package },
  { href: '/data', label: '数据中枢', icon: Database },
  { href: '/settings', label: '系统设置', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-56 border-r border-[var(--border-subtle)] bg-[var(--surface-base)]">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 px-5 border-b border-[var(--border-subtle)]">
        <Terminal className="h-4 w-4 text-[var(--accent-blue)]" />
        <span className="font-['JetBrains_Mono'] text-xs font-bold tracking-[0.08em] text-[var(--accent-blue)]">
          FACTORY <span className="font-normal text-[var(--text-muted)]">OS</span>
        </span>
      </div>

      {/* Navigation */}
      <nav className="p-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150',
                isActive
                  ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-white/[0.03]'
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom hint */}
      <div className="absolute bottom-4 left-0 right-0 px-5">
        <div className="text-[10px] text-[var(--text-muted)] font-['JetBrains_Mono']">
          Cmd+K 打开命令面板
        </div>
      </div>
    </aside>
  );
}
```

### Step 2: 创建 TopBar

```tsx
// frontend/src/components/topbar.tsx
'use client';

import { Clock } from 'lucide-react';
import { useEffect, useState } from 'react';

export function TopBar() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }));
    };
    update();
    const timer = setInterval(update, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="fixed top-0 left-56 right-0 z-30 h-14 border-b border-[var(--border-subtle)] bg-[var(--surface-base)] flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        {/* 页面标题由 PageHeader 组件管理 */}
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-[11px] font-['JetBrains_Mono'] text-[var(--text-muted)]">
          <Clock className="h-3 w-3" />
          {time}
        </div>
      </div>
    </header>
  );
}
```

### Step 3: 创建 AppShell

```tsx
// frontend/src/components/app-shell.tsx
'use client';

import { Sidebar } from './sidebar';
import { TopBar } from './topbar';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-[var(--surface-base)]">
      <Sidebar />
      <TopBar />
      <main className="pl-56 pt-14">
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
```

### Step 4: 更新 layout.tsx

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from 'next';
import './globals.css';
import { AppShell } from '@/components/app-shell';

export const metadata: Metadata = {
  title: 'Factory OS',
  description: '工厂智能管理系统',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
```

### Step 5: 创建 utils.ts（工具函数）

```ts
// frontend/src/lib/utils.ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(n: number): string {
  return `¥${n.toLocaleString('zh-CN')}`;
}

export function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`;
}
```

### Step 6: 验证

```bash
cd frontend && npm run dev
# 浏览器打开 http://localhost:3000
# 应看到左侧导航栏 + 顶部栏 + 空白内容区
```

---

## Task 0-2: PageHeader + KpiCard 组件

**文件：**
- Create: `frontend/src/components/page-header.tsx`
- Create: `frontend/src/components/kpi-card.tsx`

### Step 1: PageHeader

```tsx
// frontend/src/components/page-header.tsx
'use client';

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;  // 右侧操作区
}

export function PageHeader({ title, description, children }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            {description}
          </p>
        )}
      </div>
      {children && (
        <div className="flex items-center gap-3">
          {children}
        </div>
      )}
    </div>
  );
}
```

### Step 2: KpiCard

```tsx
// frontend/src/components/kpi-card.tsx
'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface KpiCardProps {
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'flat';
  trendLabel?: string;
  className?: string;
}

export function KpiCard({ label, value, trend, trendLabel, className }: KpiCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up'
    ? 'text-[var(--accent-green)]'
    : trend === 'down'
    ? 'text-[var(--accent-red)]'
    : 'text-[var(--text-muted)]';

  return (
    <div className={cn(
      'bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-5',
      className
    )}>
      <div className="text-xs text-[var(--text-muted)] mb-1">{label}</div>
      <div className="font-['JetBrains_Mono'] text-[clamp(1.75rem,4vw,2.5rem)] font-bold text-[var(--text-primary)] leading-tight">
        {value}
      </div>
      {trend && (
        <div className={cn('flex items-center gap-1 mt-2 text-xs', trendColor)}>
          <TrendIcon className="h-3 w-3" />
          {trendLabel && <span>{trendLabel}</span>}
        </div>
      )}
    </div>
  );
}
```

---

## Task 0-3: StatusBadge + RiskBadge + EmptyState

**文件：**
- Create: `frontend/src/components/status-badge.tsx`
- Create: `frontend/src/components/risk-badge.tsx`
- Create: `frontend/src/components/empty-state.tsx`

### Step 1: StatusBadge

```tsx
// frontend/src/components/status-badge.tsx
'use client';

import { cn } from '@/lib/utils';

type StatusType = 'success' | 'warning' | 'danger' | 'muted';

const statusConfig: Record<StatusType, { dot: string; bg: string }> = {
  success: { dot: 'bg-[var(--accent-green)]', bg: 'bg-[var(--accent-green)]/10' },
  warning: { dot: 'bg-[var(--accent-amber)]', bg: 'bg-[var(--accent-amber)]/10' },
  danger:  { dot: 'bg-[var(--accent-red)]', bg: 'bg-[var(--accent-red)]/10' },
  muted:   { dot: 'bg-[var(--text-muted)]', bg: 'bg-white/5' },
};

interface StatusBadgeProps {
  status: StatusType;
  label: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium',
      config.bg,
      className
    )}>
      <span className={cn('w-1.5 h-1.5 rounded-full', config.dot)} />
      {label}
    </span>
  );
}
```

### Step 2: RiskBadge

```tsx
// frontend/src/components/risk-badge.tsx
'use client';

import { cn } from '@/lib/utils';

interface RiskBadgeProps {
  level: 'L1' | 'L2' | 'L3' | 'L4' | 'L5';
  score?: number;
  className?: string;
}

const riskConfig = {
  L1: { color: 'text-[var(--text-muted)]', bg: 'bg-white/5' },
  L2: { color: 'text-[var(--accent-cyan)]', bg: 'bg-[var(--accent-cyan)]/10' },
  L3: { color: 'text-[var(--accent-amber)]', bg: 'bg-[var(--accent-amber)]/10' },
  L4: { color: 'text-[var(--accent-red)]', bg: 'bg-[var(--accent-red)]/10' },
  L5: { color: 'text-white', bg: 'bg-[var(--accent-red)]' },
};

export function RiskBadge({ level, score, className }: RiskBadgeProps) {
  const config = riskConfig[level];
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-[\'JetBrains_Mono\'] font-semibold',
      config.color, config.bg,
      className
    )}>
      {level}{score !== undefined && <span>· {score}</span>}
    </span>
  );
}
```

### Step 3: EmptyState

```tsx
// frontend/src/components/empty-state.tsx
'use client';

import { cn } from '@/lib/utils';
import { CheckCircle2 } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn(
      'bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center',
      className
    )}>
      <div className="flex justify-center mb-3 text-[var(--accent-green)]">
        {icon || <CheckCircle2 className="h-8 w-8" />}
      </div>
      <div className="text-sm font-medium text-[var(--text-primary)]">{title}</div>
      {description && (
        <div className="text-xs text-[var(--text-secondary)] mt-1">{description}</div>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

---

## Task 0-4: DataTable 组件（基于 @tanstack/react-table）

**文件：**
- Create: `frontend/src/components/data-table.tsx`

### Step 1: 完整 DataTable

```tsx
// frontend/src/components/data-table.tsx
'use client';

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table';
import { cn } from '@/lib/utils';

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  className?: string;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  className,
}: DataTableProps<TData, TValue>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full border-collapse">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-secondary)] bg-[var(--surface-muted)] border-b border-[var(--border-subtle)] whitespace-nowrap"
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row, i) => (
            <tr
              key={row.id}
              className={cn(
                'transition-colors duration-100',
                i % 2 === 0 ? 'bg-[var(--surface-base)]' : 'bg-[var(--surface-raised)]',
                'hover:bg-[var(--surface-overlay)]'
              )}
            >
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className="px-4 py-3 text-sm text-[var(--text-primary)] border-b border-[var(--border-subtle)]"
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## Task 0-5: DecisionCard 组件

**文件：**
- Create: `frontend/src/components/decision-card.tsx`

### Step 1: DecisionCard

```tsx
// frontend/src/components/decision-card.tsx
'use client';

import { RiskBadge } from './risk-badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Lightbulb, ChevronRight } from 'lucide-react';
import type { Decision } from '@/types';

interface DecisionCardProps {
  decision: Decision;
  onAction?: (action: string, decisionId: string) => void;
  className?: string;
}

export function DecisionCard({ decision, onAction, className }: DecisionCardProps) {
  return (
    <div className={cn(
      'bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl overflow-hidden transition-all duration-150',
      'hover:border-[var(--border-default)]',
      className
    )}>
      {/* Main content */}
      <div className="p-5 flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <RiskBadge level={`L${decision.level}` as any} score={decision.score} />
            <span className="text-[10px] font-['JetBrains_Mono'] text-[var(--text-muted)]">
              {decision.source}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            {decision.title}
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
            {decision.description}
          </p>
        </div>
      </div>

      {/* AI insight bar */}
      <div className="px-5 py-3 bg-[var(--surface-overlay)] border-t border-[var(--border-subtle)] flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Lightbulb className="h-3 w-3 text-[var(--accent-amber)] flex-shrink-0" />
          <span className="text-[11px] text-[var(--text-secondary)]">
            <strong className="text-[var(--text-primary)]">等待你的决定</strong>
            {decision.suggested_actions && decision.suggested_actions.length > 0 && (
              <> · {decision.suggested_actions.filter(a => a.action !== 'dismiss' && a.action !== 'view_detail').length} 个操作选项</>
            )}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {decision.suggested_actions?.slice(0, 2).map((action) => (
            <Button
              key={action.action}
              size="sm"
              variant={action.action === 'dismiss' ? 'ghost' : 'default'}
              className="text-xs h-7 px-3"
              onClick={() => onAction?.(action.action, decision.id)}
            >
              {action.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## Task 0-6: InsightCard 组件

**文件：**
- Create: `frontend/src/components/insight-card.tsx`

```tsx
// frontend/src/components/insight-card.tsx
'use client';

import { cn } from '@/lib/utils';
import { AlertTriangle, Info } from 'lucide-react';
import type { Insight } from '@/types';

interface InsightCardProps {
  insight: Insight;
  className?: string;
}

export function InsightCard({ insight, className }: InsightCardProps) {
  const isHighRisk = insight.level >= 3;
  const Icon = isHighRisk ? AlertTriangle : Info;
  const iconColor = isHighRisk ? 'text-[var(--accent-amber)]' : 'text-[var(--accent-cyan)]';

  return (
    <div className={cn(
      'flex items-start gap-2 py-1.5',
      className
    )}>
      <Icon className={cn('h-3.5 w-3.5 mt-0.5 flex-shrink-0', iconColor)} />
      <span className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
        {insight.text}
      </span>
    </div>
  );
}
```

---

## Task 0-7: ContextStrip 组件

**文件：**
- Create: `frontend/src/components/context-strip.tsx`

```tsx
// frontend/src/components/context-strip.tsx
'use client';

import { InsightCard } from './insight-card';
import { cn } from '@/lib/utils';
import { Sparkles } from 'lucide-react';
import type { Insight } from '@/types';

interface ContextStripProps {
  insights: Insight[];
  className?: string;
}

export function ContextStrip({ insights, className }: ContextStripProps) {
  if (!insights || insights.length === 0) return null;

  return (
    <div className={cn(
      'flex items-center gap-3 px-4 py-2 bg-[var(--surface-overlay)] border border-[var(--border-subtle)] rounded-lg mb-4',
      className
    )}>
      <Sparkles className="h-3.5 w-3.5 text-[var(--accent-blue)] flex-shrink-0" />
      <div className="flex-1 flex items-center gap-4 overflow-x-auto">
        {insights.slice(0, 3).map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    </div>
  );
}
```

---

## Task 0-8: TypeScript 类型定义

**文件：**
- Create: `frontend/src/types/index.ts`

```ts
// frontend/src/types/index.ts

export interface Event {
  id: string;
  type: string;
  entity_type: string;
  entity_id: string;
  title: string;
  description: string;
  source: string;
  confidence: number;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface Decision {
  id: string;
  event_id: string;
  level: number;
  score: number;
  title: string;
  description: string;
  status: 'pending' | 'approved' | 'rejected' | 'dismissed' | 'executing' | 'executed' | 'failed';
  source: string;
  confidence: number;
  roles: string[];
  context_filter: string;
  suggested_actions: Action[];
  created_at: string;
  expires_at?: string;
}

export interface Insight {
  id: string;
  event_id: string;
  level: number;
  score: number;
  confidence: number;
  text: string;
  context_filter: string;
  expires_at: string;
}

export interface Action {
  action: string;
  label: string;
  description?: string;
  payload: Record<string, unknown>;
  confirmation_required?: boolean;
  allowed_roles?: string[];
}

export interface Notification {
  id: string;
  event_id: string;
  decision_id?: string;
  insight_id?: string;
  channel: 'decision_center' | 'context_strip' | 'data_log';
  target: string;
  display_text: string;
  display_level: number;
  display_score: number;
  created_at: string;
  read_at?: string;
}

export interface KpiData {
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'flat';
  trendLabel?: string;
}

export interface PageContext {
  role: string;
  current_page: string;
  current_focus?: string;
}
```

---

## Task 0-9: API 客户端

**文件：**
- Create: `frontend/src/lib/api.ts`

```ts
// frontend/src/lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

import type { Decision, Insight, Action, Notification } from '@/types';

export const api = {
  // Decision Center
  getDecisions(params: {
    role?: string;
    page?: string;
    level_min?: number;
    status?: string;
  }): Promise<{ items: Decision[]; total: number; unread_count: number }> {
    const qs = new URLSearchParams();
    if (params.role) qs.set('role', params.role);
    if (params.page) qs.set('page', params.page);
    if (params.level_min) qs.set('level_min', String(params.level_min));
    if (params.status) qs.set('status', params.status);
    return fetchApi(`/api/decision-center?${qs}`);
  },

  // Context Strip
  getContextStrip(params: {
    page: string;
    role?: string;
    limit?: number;
  }): Promise<{ items: Insight[] }> {
    const qs = new URLSearchParams();
    qs.set('page', params.page);
    if (params.role) qs.set('role', params.role);
    if (params.limit) qs.set('limit', String(params.limit));
    return fetchApi(`/api/context-strip?${qs}`);
  },

  // Events
  postEvent(event: {
    type: string;
    entity_type: string;
    entity_id: string;
    title: string;
    description?: string;
    source: string;
    confidence: number;
    timestamp: string;
    metadata?: Record<string, unknown>;
  }): Promise<{ event_id: string; decisions: string[]; insights: string[] }> {
    return fetchApi('/api/events', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  },

  // Actions
  executeAction(req: {
    action: string;
    decision_id: string;
    idempotency_key: string;
    payload?: Record<string, unknown>;
    user?: string;
    note?: string;
  }): Promise<{ success: boolean; decision_status: string; outcome_id?: string; message: string }> {
    return fetchApi('/api/actions', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },
};
```

---

## Task 0-10: tailwind.config.ts 补充

```ts
// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
```

---

## Task 0-11: 首页占位（验证布局）

**文件：**
- Modify: `frontend/src/app/page.tsx`

```tsx
// frontend/src/app/page.tsx
'use client';

import { PageHeader } from '@/components/page-header';
import { DecisionCard } from '@/components/decision-card';
import { ContextStrip } from '@/components/context-strip';
import { EmptyState } from '@/components/empty-state';
import { CheckCircle2 } from 'lucide-react';

export default function HomePage() {
  // Phase 2 时会替换为真实 API 数据
  const decisions: any[] = [];
  const insights: any[] = [];

  return (
    <div>
      <PageHeader
        title="指挥中心"
        description="今天需要你决定的事项"
      />

      <ContextStrip insights={insights} />

      {decisions.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="h-8 w-8" />}
          title="今天暂无待处理事项"
          description="系统运行正常"
        />
      ) : (
        <div className="space-y-3">
          {decisions.map((d) => (
            <DecisionCard key={d.id} decision={d} />
          ))}
        </div>
      )}
    </div>
  );
}
```

### 验证最终效果

```bash
cd frontend && npm run dev
# 浏览器打开 http://localhost:3000
# 应看到:
# - 左侧: 深色导航栏，7 个菜单项，FACTORY OS logo
# - 顶部: 空 Header，右侧显示时间
# - 内容: "指挥中心" 标题，空态展示"今天暂无待处理事项"
```

---

## Task 0-12: 安装 shadcn/ui 组件并确认可用

```bash
cd frontend

# 确保 shadcn/ui 组件已安装
npx shadcn@latest add button card input select table badge separator tabs sheet command dialog toast -y

# 验证编译
npm run build
# 应输出: ✓ Compiled successfully
```

---

## Phase 0 完成检查清单

完成后逐项确认：

- [ ] `npm run dev` 启动正常，浏览器能访问 localhost:3000
- [ ] 左侧导航栏 7 个菜单项均正确显示
- [ ] 导航栏选中态高亮（当前路由）
- [ ] 顶部栏显示当前时间
- [ ] AppShell 布局正确（侧边栏 224px + 内容区自适应）
- [ ] 空态页面正常展示
- [ ] `npm run build` 无错误
- [ ] 所有 Streamlit 文件已删除
- [ ] 提交 commit: `feat: Phase 0 — Design System 组件库 + 项目脚手架`

---

## 各 Task 执行顺序

```
Task 0-1: AppShell + Sidebar + TopBar（布局骨架）
    ↓
Task 0-2: PageHeader + KpiCard（基础展示组件）
    ↓
Task 0-3: StatusBadge + RiskBadge + EmptyState（辅助组件）
    ↓
Task 0-4: DataTable（数据展示）
    ↓
Task 0-5: DecisionCard（业务组件）
    ↓
Task 0-6: InsightCard（业务组件）
    ↓
Task 0-7: ContextStrip（业务组件）
    ↓
Task 0-8: TypeScript 类型定义
    ↓
Task 0-9: API 客户端
    ↓
Task 0-10: tailwind.config.ts
    ↓
Task 0-11: 首页占位验证
    ↓
Task 0-12: shadcn/ui + 构建验证
```
