# Factory OS Phase 3: 业务中心

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 依赖: Phase 0（组件库）+ Phase 1（API 就绪）

---

## 架构说明

4 个业务中心使用统一模式：

```
Page
 ├── ContextStrip（从 /api/context-strip 获取）
 ├── 子标签栏（searchParams tab 切换）
 └── 标签对应内容区
     ├── KpiRow（4 个 KpiCard）
     ├── DataTable（业务数据）
     └── 图表（Recharts）
```

子标签切换使用 URL searchParam，不创建独立路由路径：
`/production?tab=today`、`/production?tab=orders`

---

## Task 3-1: 生产中心

**文件：**
- Create: `frontend/src/app/production/page.tsx`

```tsx
// frontend/src/app/production/page.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';
import { KpiCard } from '@/components/kpi-card';
import { DataTable } from '@/components/data-table';
import { ContextStrip } from '@/components/context-strip';
import { StatusBadge } from '@/components/status-badge';
import { api } from '@/lib/api';
import { createColumnHelper } from '@tanstack/react-table';
import type { Insight } from '@/types';

// ── 子标签定义 ──
const TABS = [
  { key: 'today', label: '今日总览' },
  { key: 'orders', label: '工单列表' },
  { key: 'efficiency', label: '效率看板' },
  { key: 'dispatch', label: '派工建议' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

// ── 工单数据类型 ──
interface WorkOrder {
  id: string;
  device_model: string;
  status: string;
  days_remaining: number | null;
  risk_level: string;
}

const columnHelper = createColumnHelper<WorkOrder>();

const orderColumns = [
  columnHelper.accessor('id', { header: '工单号', cell: (info) => (
    <span className="font-['JetBrains_Mono'] text-xs">{info.getValue()}</span>
  )}),
  columnHelper.accessor('device_model', { header: '设备型号' }),
  columnHelper.accessor('status', { header: '状态', cell: (info) => {
    const status = info.getValue();
    const badgeStatus = status === '生产中' ? 'success' : status === '待开始' ? 'muted' : 'warning';
    return <StatusBadge status={badgeStatus} label={status} />;
  }}),
  columnHelper.accessor('days_remaining', { header: '剩余天数', cell: (info) => {
    const days = info.getValue();
    if (days === null) return <span className="text-[var(--text-muted)]">--</span>;
    const color = days < 0 ? 'var(--accent-red)' : days <= 3 ? 'var(--accent-amber)' : 'var(--text-primary)';
    return <span className="font-['JetBrains_Mono'] text-xs" style={{ color }}>{days < 0 ? `已超期 ${-days}天` : `${days}天`}</span>;
  }}),
  columnHelper.accessor('risk_level', { header: '风险', cell: (info) => {
    const level = info.getValue();
    if (!level || level === '灰') return <span className="text-[var(--text-muted)]">--</span>;
    return <StatusBadge status={level === '紫' || level === '红' ? 'danger' : 'warning'} label={level} />;
  }}),
];

export default function ProductionPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'today';

  const [insights, setInsights] = useState<Insight[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [kpiData, setKpiData] = useState({ active: 0, risk: 0, urgent: 0, delayed: 0 });

  useEffect(() => {
    loadData();
  }, [currentTab]);

  async function loadData() {
    try {
      const [insRes, orderRes] = await Promise.all([
        api.getContextStrip({ page: 'production', role: 'admin', limit: 3 }),
        fetch('http://localhost:8000/api/business/work-orders?limit=50').then(r => r.json()),
      ]);
      setInsights(insRes.items);

      const ordersList: WorkOrder[] = Array.isArray(orderRes) ? orderRes : [];
      setOrders(ordersList);
      setKpiData({
        active: ordersList.filter(o => o.status === '生产中').length,
        risk: ordersList.filter(o => o.risk_level === '紫' || o.risk_level === '红').length,
        urgent: ordersList.filter(o => o.days_remaining !== null && o.days_remaining <= 3 && o.days_remaining >= 0).length,
        delayed: ordersList.filter(o => o.days_remaining !== null && o.days_remaining < 0).length,
      });
    } catch (err) {
      console.error('加载生产中心数据失败:', err);
    }
  }

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/production?${params}`);
  }, [router, searchParams]);

  return (
    <div>
      <PageHeader title="生产中心" description="工单进度与生产状态总览" />

      <ContextStrip insights={insights} />

      {/* Tabs */}
      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {currentTab === 'today' && (
        <div>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <KpiCard label="活跃工单" value={kpiData.active} />
            <KpiCard label="高风险" value={kpiData.risk} trend={kpiData.risk > 0 ? 'up' : 'flat'} trendLabel={kpiData.risk > 0 ? '需关注' : '正常'} />
            <KpiCard label="交期紧迫" value={kpiData.urgent} trend={kpiData.urgent > 0 ? 'up' : 'flat'} trendLabel="≤3天" />
            <KpiCard label="已超期" value={kpiData.delayed} trend={kpiData.delayed > 0 ? 'down' : 'flat'} trendLabel={kpiData.delayed > 0 ? '需处理' : '无'} />
          </div>
          <DataTable columns={orderColumns} data={orders.slice(0, 10)} />
        </div>
      )}

      {currentTab === 'orders' && (
        <DataTable columns={orderColumns} data={orders} />
      )}

      {currentTab === 'efficiency' && (
        <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
          效率看板数据加载中...
        </div>
      )}

      {currentTab === 'dispatch' && (
        <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
          派工建议数据加载中...
        </div>
      )}
    </div>
  );
}
```

---

## Task 3-2: 设备中心

**文件：**
- Create: `frontend/src/app/equipment/page.tsx`

```tsx
// frontend/src/app/equipment/page.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';
import { KpiCard } from '@/components/kpi-card';
import { DataTable } from '@/components/data-table';
import { ContextStrip } from '@/components/context-strip';
import { StatusBadge } from '@/components/status-badge';
import { createColumnHelper } from '@tanstack/react-table';
import type { Insight } from '@/types';

const TABS = [
  { key: 'list', label: '设备列表' },
  { key: 'analysis', label: '工时分析' },
  { key: 'maintenance', label: '保养提醒' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

interface Equipment {
  id: string;
  name: string;
  model: string;
  status: string;
}

const columnHelper = createColumnHelper<Equipment>();
const columns = [
  columnHelper.accessor('id', { header: '编号', cell: (info) => <span className="font-['JetBrains_Mono'] text-xs">{info.getValue()}</span> }),
  columnHelper.accessor('name', { header: '名称' }),
  columnHelper.accessor('model', { header: '型号' }),
  columnHelper.accessor('status', { header: '状态', cell: (info) => {
    const s = info.getValue();
    return <StatusBadge status={s === '运行' ? 'success' : s === '停机' ? 'danger' : 'muted'} label={s} />;
  }}),
];

export default function EquipmentPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'list';

  const [insights, setInsights] = useState<Insight[]>([]);
  const [equipment, setEquipment] = useState<Equipment[]>([]);

  useEffect(() => {
    Promise.all([
      api.getContextStrip({ page: 'equipment', role: 'admin', limit: 3 }),
      fetch('http://localhost:8000/api/business/equipment').then(r => r.json()),
    ]).then(([insRes, equipRes]) => {
      setInsights(insRes.items);
      if (Array.isArray(equipRes)) setEquipment(equipRes);
    });
  }, []);

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/equipment?${params}`);
  }, [router, searchParams]);

  const runningCount = equipment.filter(e => e.status === '运行').length;

  return (
    <div>
      <PageHeader title="设备中心" description="设备状态与工时分析" />
      <ContextStrip insights={insights} />

      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)]">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}>{tab.label}</button>
        ))}
      </div>

      {currentTab === 'list' && (
        <div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <KpiCard label="设备总数" value={equipment.length} />
            <KpiCard label="运行中" value={runningCount} trend="flat" />
            <KpiCard label="停机" value={equipment.length - runningCount} trend={equipment.length - runningCount > 0 ? 'down' : 'flat'} />
          </div>
          <DataTable columns={columns} data={equipment} />
        </div>
      )}

      {(currentTab === 'analysis' || currentTab === 'maintenance') && (
        <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
          {currentTab === 'analysis' ? '工时分析数据加载中...' : '保养提醒数据加载中...'}
        </div>
      )}
    </div>
  );
}
```

---

## Task 3-3: 人员中心

**文件：**
- Create: `frontend/src/app/personnel/page.tsx`

```tsx
// frontend/src/app/personnel/page.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';
import { KpiCard } from '@/components/kpi-card';
import { DataTable } from '@/components/data-table';
import { ContextStrip } from '@/components/context-strip';
import { createColumnHelper } from '@tanstack/react-table';
import type { Insight } from '@/types';

const TABS = [
  { key: 'dashboard', label: '在岗看板' },
  { key: 'efficiency', label: '效率排行' },
  { key: 'skills', label: '技能矩阵' },
  { key: 'roster', label: '在职清单' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

interface Employee {
  id: string;
  name: string;
  department: string;
  position: string;
  status: string;
}

const columnHelper = createColumnHelper<Employee>();
const columns = [
  columnHelper.accessor('name', { header: '姓名' }),
  columnHelper.accessor('department', { header: '部门' }),
  columnHelper.accessor('position', { header: '岗位' }),
  columnHelper.accessor('status', { header: '状态' }),
];

export default function PersonnelPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'dashboard';

  const [insights, setInsights] = useState<Insight[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);

  useEffect(() => {
    Promise.all([
      api.getContextStrip({ page: 'personnel', role: 'admin', limit: 3 }),
      fetch('http://localhost:8000/api/business/employees').then(r => r.json()),
    ]).then(([insRes, empRes]) => {
      setInsights(insRes.items);
      if (Array.isArray(empRes)) setEmployees(empRes);
    });
  }, []);

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/personnel?${params}`);
  }, [router, searchParams]);

  return (
    <div>
      <PageHeader title="人员中心" description="人员状态与效率分析" />
      <ContextStrip insights={insights} />

      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)]">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}>{tab.label}</button>
        ))}
      </div>

      {currentTab === 'dashboard' && (
        <div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <KpiCard label="在职人数" value={employees.length} />
            <KpiCard label="在岗" value={employees.filter(e => e.status === '在岗').length} trend="flat" />
            <KpiCard label="出差/外勤" value={employees.filter(e => e.status !== '在岗').length} trend="flat" />
          </div>
          <DataTable columns={columns} data={employees} />
        </div>
      )}

      {(currentTab !== 'dashboard') && (
        <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
          {currentTab === 'efficiency' ? '效率排行数据加载中...' : currentTab === 'skills' ? '技能矩阵数据加载中...' : '在职清单数据加载中...'}
        </div>
      )}
    </div>
  );
}
```

---

## Task 3-4: 物料中心

**文件：**
- Create: `frontend/src/app/materials/page.tsx`

```tsx
// frontend/src/app/materials/page.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageHeader } from '@/components/page-header';
import { KpiCard } from '@/components/kpi-card';
import { DataTable } from '@/components/data-table';
import { ContextStrip } from '@/components/context-strip';
import { StatusBadge } from '@/components/status-badge';
import { createColumnHelper } from '@tanstack/react-table';
import type { Insight } from '@/types';

const TABS = [
  { key: 'shortages', label: '缺料跟踪' },
  { key: 'bom', label: 'BOM展开' },
  { key: 'stock', label: '库存看板' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

interface Shortage {
  order_id: string;
  material_name: string;
  quantity: number;
  status: string;
}

const columnHelper = createColumnHelper<Shortage>();
const columns = [
  columnHelper.accessor('order_id', { header: '工单', cell: (info) => <span className="font-['JetBrains_Mono'] text-xs">{info.getValue()}</span> }),
  columnHelper.accessor('material_name', { header: '缺料名称' }),
  columnHelper.accessor('quantity', { header: '缺少数量', cell: (info) => <span className="font-['JetBrains_Mono'] text-xs">{info.getValue()}</span> }),
  columnHelper.accessor('status', { header: '状态', cell: (info) => {
    const s = info.getValue();
    return <StatusBadge status={s === '待采购' ? 'danger' : s === '采购中' ? 'warning' : 'success'} label={s} />;
  }}),
];

export default function MaterialsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'shortages';

  const [insights, setInsights] = useState<Insight[]>([]);
  const [shortages, setShortages] = useState<Shortage[]>([]);

  useEffect(() => {
    Promise.all([
      api.getContextStrip({ page: 'materials', role: 'admin', limit: 3 }),
      fetch('http://localhost:8000/api/business/shortages?limit=50').then(r => r.json()),
    ]).then(([insRes, shortRes]) => {
      setInsights(insRes.items);
      if (Array.isArray(shortRes)) setShortages(shortRes);
    });
  }, []);

  const switchTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.push(`/materials?${params}`);
  }, [router, searchParams]);

  return (
    <div>
      <PageHeader title="物料中心" description="缺料与库存状态" />
      <ContextStrip insights={insights} />

      <div className="flex gap-6 mb-6 border-b border-[var(--border-subtle)]">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => switchTab(tab.key)}
            className={`pb-2 text-sm font-medium transition-colors ${
              currentTab === tab.key
                ? 'text-[var(--accent-blue)] border-b-2 border-[var(--accent-blue)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}>{tab.label}</button>
        ))}
      </div>

      {currentTab === 'shortages' && (
        <div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <KpiCard label="缺料工单" value={shortages.length} />
            <KpiCard label="待采购" value={shortages.filter(s => s.status === '待采购').length} trend={shortages.filter(s => s.status === '待采购').length > 0 ? 'down' : 'flat'} />
            <KpiCard label="采购中" value={shortages.filter(s => s.status === '采购中').length} trend="flat" />
          </div>
          <DataTable columns={columns} data={shortages} />
        </div>
      )}

      {(currentTab !== 'shortages') && (
        <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] rounded-xl p-6 text-center text-[var(--text-muted)] text-sm">
          {currentTab === 'bom' ? 'BOM展开数据加载中...' : '库存看板数据加载中...'}
        </div>
      )}
    </div>
  );
}
```

---

## Phase 3 完成检查清单

- [ ] `/production` 页面正常展示，4 个标签可切换
- [ ] `/equipment` 页面正常展示，3 个标签可切换
- [ ] `/personnel` 页面正常展示，4 个标签可切换
- [ ] `/materials` 页面正常展示，3 个标签可切换
- [ ] 每个页面都显示 AI Context Strip
- [ ] 标签切换通过 URL searchParams，刷新后停留在当前标签
- [ ] DataTable 显示正确数据
- [ ] KpiCard 统计正确
- [ ] 提交 commit: `feat: Phase 3 — 4 个业务中心页面`
