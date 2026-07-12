# Factory OS Phase 4: 数据中枢 + 系统设置

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 依赖: Phase 3（页面模式参考）

---

## Task 4-1: 数据中枢

**文件：**
- Create: `frontend/src/app/data/page.tsx`

```tsx
// frontend/src/app/data/page.tsx
'use client';

import { useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';
import { ContextStrip } from '@/components/context-strip';
import type { Insight } from '@/types';

const TABS = [
  { key: 'causality', label: '因果分析' },
  { key: 'tracing', label: '来源追溯' },
  { key: 'ontology', label: '本体视图' },
  { key: 'sync', label: '数据同步' },
  { key: 'inbox', label: '收件箱管理' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

export default function DataPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'causality';
  const [insights] = useState<Insight[]>([]);

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/data?${params}`);
  }, [router, searchParams]);

  return (
    <div>
      <PageHeader title="数据中枢" description="数据分析和系统管理" />
      <ContextStrip insights={insights} />

      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)] overflow-x-auto">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium whitespace-nowrap transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}>{tab.label}</button>
        ))}
      </div>

      <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
        {currentTab === 'causality' && '因果分析 — 追踪事件之间的因果关系（后续迭代）'}
        {currentTab === 'tracing' && '来源追溯 — 追踪数据来源与变更历史（后续迭代）'}
        {currentTab === 'ontology' && '本体视图 — 实体关系图（后续迭代）'}
        {currentTab === 'sync' && '数据同步 — 管理外部数据源同步（后续迭代）'}
        {currentTab === 'inbox' && '收件箱管理 — AI 收件箱分类与处理（后续迭代）'}
      </div>
    </div>
  );
}
```

---

## Task 4-2: 系统设置

**文件：**
- Create: `frontend/src/app/settings/page.tsx`

```tsx
// frontend/src/app/settings/page.tsx
'use client';

import { useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';

const TABS = [
  { key: 'employees', label: '员工管理' },
  { key: 'erp', label: 'ERP同步' },
  { key: 'db', label: '数据库配置' },
  { key: 'llm', label: 'LLM配置' },
  { key: 'params', label: '参数管理' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

export default function SettingsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'employees';

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/settings?${params}`);
  }, [router, searchParams]);

  return (
    <div>
      <PageHeader title="系统设置" description="系统配置与管理" />

      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)] overflow-x-auto">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium whitespace-nowrap transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}>{tab.label}</button>
        ))}
      </div>

      <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
        {currentTab === 'employees' && '员工管理 — 添加/编辑/禁用员工信息（后续迭代）'}
        {currentTab === 'erp' && 'ERP同步 — 配置 ERP 连接参数与同步策略（后续迭代）'}
        {currentTab === 'db' && '数据库配置 — 数据库连接与维护（后续迭代）'}
        {currentTab === 'llm' && 'LLM配置 — AI 模型参数配置（后续迭代）'}
        {currentTab === 'params' && '参数管理 — 系统运行参数配置（后续迭代）'}
      </div>
    </div>
  );
}
```

---

## Phase 4 完成检查清单

- [ ] `/data` 页面正常展示，5 个标签可切换
- [ ] `/settings` 页面正常展示，5 个标签可切换
- [ ] 标签切换通过 URL searchParams
- [ ] 提交 commit: `feat: Phase 4 — 数据中枢 + 系统设置`
