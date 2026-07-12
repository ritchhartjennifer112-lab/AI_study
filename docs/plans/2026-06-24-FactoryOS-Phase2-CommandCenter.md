# Factory OS Phase 2: 指挥中心

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 依赖: Phase 0（组件库）+ Phase 1（API 就绪）

---

## Task 2-1: 指挥中心首页（Decision Center）

**文件：**
- Rewrite: `frontend/src/app/page.tsx`

```tsx
// frontend/src/app/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/page-header';
import { DecisionCard } from '@/components/decision-card';
import { ContextStrip } from '@/components/context-strip';
import { KpiCard } from '@/components/kpi-card';
import { EmptyState } from '@/components/empty-state';
import { api } from '@/lib/api';
import type { Decision, Insight } from '@/types';

export default function HomePage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [decRes, insRes] = await Promise.all([
        api.getDecisions({ role: 'admin', page: '', level_min: 4, status: 'pending' }),
        api.getContextStrip({ page: '', role: 'admin', limit: 3 }),
      ]);
      setDecisions(decRes.items);
      setInsights(insRes.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(action: string, decisionId: string) {
    try {
      const idempotencyKey = `fe_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      await api.executeAction({
        action,
        decision_id: decisionId,
        idempotency_key: idempotencyKey,
        user: '管理员',
      });
      // 刷新列表
      loadData();
    } catch (err) {
      console.error('Action failed:', err);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-[var(--text-muted)]">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-[var(--accent-red)]">错误: {error}</div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="指挥中心"
        description={`今天需要你决定 ${decisions.length} 件事`}
      />

      <ContextStrip insights={insights} />

      {decisions.length === 0 ? (
        <EmptyState
          title="今天暂无待处理事项"
          description="系统运行正常，没有需要你决定的事项"
        />
      ) : (
        <div className="space-y-2">
          {decisions.map((d) => (
            <DecisionCard
              key={d.id}
              decision={d}
              onAction={handleAction}
            />
          ))}
        </div>
      )}

      {/* Factory Index */}
      <div className="mt-8 flex items-center justify-end">
        <div className="text-right">
          <div className="text-[10px] text-[var(--text-muted)] font-['JetBrains_Mono']">
            FACTORY INDEX
          </div>
          <div className="text-lg font-bold font-['JetBrains_Mono'] text-[var(--accent-blue)]">
            {decisions.length === 0 ? '96' : 100 - decisions.length * 3}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 验证

```bash
# 确保后端运行
uvicorn api.main:app --reload --port 8000

# 另一个终端
cd frontend && npm run dev
```

浏览器打开 `http://localhost:3000`，应看到：
- 左侧导航栏 + 顶部栏
- AI Context Strip（如果有 Insight）
- Decision Card 列表（如果有 Decision）
- 空态展示"今天暂无待处理事项"（无 Decision 时）
- 右上角 Factory Index

---

## Task 2-2: 投递测试

**推送测试数据验证完整链路：**

```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "delay",
    "entity_type": "work_order",
    "entity_id": "WO-1827",
    "title": "WO-1827 铜牌仓B 预计延期2天",
    "description": "当前进度62%，交期剩余3天。涉及金额 ¥126,000",
    "source": "erp_sync",
    "confidence": 0.95,
    "timestamp": "2026-06-24T08:00:00Z"
  }'

# 再推送一个缺料事件
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "shortage",
    "entity_type": "material",
    "entity_id": "A料",
    "title": "A料库存不足，已影响3个工单",
    "description": "建议优先采购，预计 ¥8,500",
    "source": "erp_sync",
    "confidence": 0.92,
    "timestamp": "2026-06-24T09:00:00Z"
  }'

# 刷新前端页面，应看到两条 Decision Card
```

---

## Task 2-3: Phase 2 完成检查清单

- [ ] 首页展示 Decision Center
- [ ] Decision Card 正确显示 L4-L5 决策项
- [ ] AI Context Strip 展示 L2-L3 洞察
- [ ] 空态展示"今天暂无待处理事项"
- [ ] Decision Card 上的按钮可点击并调用 API
- [ ] 执行操作后列表刷新
- [ ] Factory Index 小字展示
- [ ] 加载态 + 错误态处理
- [ ] 提交 commit: `feat: Phase 2 — 指挥中心 Decision Center 首页`
