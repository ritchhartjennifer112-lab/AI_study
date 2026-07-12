# Factory OS Phase 5: AI 神经系统

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 依赖: Phase 2（Command Center）+ Phase 3（Business Centers）

---

## Phase 5 说明

AI 在 Factory OS 中不是独立页面，而是嵌入到每个页面的神经系统。Phase 5 的工作是：

1. **AI Context Strip 全页面生效** — 确保所有页面（production/equipment/personnel/materials）的 Context Strip 连接到真实 API
2. **Decision History** — 在 Decision 完成后跟踪结果（调用 core/*.py 中的评估逻辑）
3. **Cmd+K 全局命令面板** — 快速导航 + 查询入口（调用 IntentRouter + ReActAgent）
4. **Decision Center 自动填充** — 将 core/delivery_risk.py 等现有评估转为 Event 推送到引擎

---

## Task 5-1: Context Strip 全页面接入

**说明：** Phase 2 和 Phase 3 已经在前端接了 Context Strip API，但需要：
1. 确认所有页面的 `current_page` 参数正确传递
2. 后端按时推送事件（不只是手动 curl）

### 后端自动事件推送（在 EventService 中添加）

```python
# api/services/event_service.py 追加方法
def auto_push_risks(self):
    """从 core/delivery_risk.py 自动推送风险事件。"""
    from core.delivery_risk import calc_all_risks
    from datetime import datetime

    try:
        risks = calc_all_risks()
        for risk in (risks or [])[:10]:  # 限量
            order_id = risk.get("order_id", "")
            if not order_id:
                continue

            # 检查是否已推送过
            existing = self.db.execute(
                text("SELECT id FROM events WHERE entity_id = :eid AND type = 'delay' AND timestamp >= :ts"),
                {"eid": order_id, "ts": datetime.utcnow().strftime("%Y-%m-%d 00:00:00")},
            ).fetchone()
            if existing:
                continue  # 今天已推送过

            event = EventCreate(
                type="delay",
                entity_type="work_order",
                entity_id=order_id,
                title=f"{order_id} 交付延期风险",
                description=risk.get("risk_reason", ""),
                source="erp_sync",
                confidence=0.95,
                timestamp=datetime.utcnow(),
                metadata={
                    "risk_level": risk.get("risk_level", ""),
                    "days_remaining": risk.get("days_remaining"),
                },
            )
            self.process_event(event)
    except Exception as e:
        print(f"[AutoPush] 风险推送失败: {e}")
```

在 `api/routers/events.py` 添加触发端点：

```python
@router.post("/events/auto-push")
def auto_push_events(db: Session = Depends(get_db)):
    """自动从现有业务逻辑推送事件。"""
    service = EventService(db)
    service.auto_push_risks()
    return {"status": "ok", "message": "自动推送完成"}
```

前端可定时调用（放在 layout 或 page 的 useEffect 中）：

```tsx
// frontend/src/app/layout.tsx — 添加客户端组件
'use client';
import { useEffect } from 'react';
function AutoEventPusher() {
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        await fetch('http://localhost:8000/api/events/auto-push', { method: 'POST' });
      } catch {}
    }, 300000); // 每 5 分钟自动推送一次
    return () => clearInterval(timer);
  }, []);
  return null;
}
```

---

## Task 5-2: Cmd+K 全局命令面板

**文件：**
- Create: `frontend/src/components/command-palette.tsx`
- Modify: `frontend/src/app/layout.tsx`（注册全局事件）

```tsx
// frontend/src/components/command-palette.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Command } from 'lucide-react';

const NAV_ITEMS = [
  { label: '指挥中心', href: '/', keywords: '首页 dashboard home' },
  { label: '生产中心', href: '/production', keywords: '生产 工单 效率 派工' },
  { label: '设备中心', href: '/equipment', keywords: '设备 机器 保养 维修' },
  { label: '人员中心', href: '/personnel', keywords: '人员 员工 考勤 技能' },
  { label: '物料中心', href: '/materials', keywords: '物料 缺料 库存 BOM' },
  { label: '数据中枢', href: '/data', keywords: '数据 分析 同步 收件箱' },
  { label: '系统设置', href: '/settings', keywords: '设置 配置 ERP 数据库' },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const filtered = query
    ? NAV_ITEMS.filter(item =>
        item.label.includes(query) ||
        item.keywords.includes(query)
      )
    : NAV_ITEMS;

  const handleSelect = useCallback((href: string) => {
    router.push(href);
    setOpen(false);
    setQuery('');
  }, [router]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-50" onClick={() => setOpen(false)} />

      {/* Panel */}
      <div className="fixed top-[15%] left-1/2 -translate-x-1/2 w-[480px] max-w-[90vw] z-50">
        <div className="bg-[var(--surface-raised)] border border-[var(--border-default)] rounded-xl shadow-2xl overflow-hidden">
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-subtle)]">
            <Search className="h-4 w-4 text-[var(--text-muted)]" />
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="搜索页面或输入命令..."
              className="flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
            />
            <kbd className="text-[10px] text-[var(--text-muted)] font-['JetBrains_Mono'] bg-[var(--surface-muted)] px-1.5 py-0.5 rounded">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="py-2 max-h-64 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-3 text-sm text-[var(--text-muted)]">无匹配结果</div>
            ) : (
              filtered.map(item => (
                <button
                  key={item.href}
                  onClick={() => handleSelect(item.href)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--text-primary)] hover:bg-[var(--surface-overlay)] transition-colors text-left"
                >
                  <Command className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  {item.label}
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}
```

在 `layout.tsx` 中注册：

```tsx
// frontend/src/app/layout.tsx — 添加
import { CommandPalette } from '@/components/command-palette';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>
          <CommandPalette />
          {children}
        </AppShell>
      </body>
    </html>
  );
}
```

---

## Task 5-3: Decision History 追踪

**文件：**
- Create: `api/routers/decision_history.py`
- Modify: `api/main.py`

```python
# api/routers/decision_history.py
"""Decision History — 跟踪 AI 决策准确度。"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import get_db

router = APIRouter(prefix="/api", tags=["decisions"])


class OutcomeRecord(BaseModel):
    decision_id: str
    ai_predicted_impact: str
    ai_predicted_financial: float = 0
    actual_impact: str = ""
    actual_financial: float | None = None
    accuracy_score: int  # 1-5
    accuracy_feedback: str = ""
    time_to_decision: int = 0  # 分钟
    prevented_loss: float = 0.0


@router.post("/decision-outcomes")
def record_outcome(outcome: OutcomeRecord, db: Session = Depends(get_db)):
    """记录决策结果。"""
    now = datetime.utcnow()
    db.execute(
        text("""
            INSERT INTO decision_outcomes
            (id, decision_id, ai_predicted_impact, ai_predicted_financial,
             actual_impact, actual_financial, accuracy_score, accuracy_feedback,
             time_to_decision, prevented_loss, created_at)
            VALUES (:id, :did, :aipi, :aipf, :acti, :actf, :asc, :afb, :ttd, :pl, :now)
        """),
        {
            "id": f"out_{outcome.decision_id}",
            "did": outcome.decision_id,
            "aipi": outcome.ai_predicted_impact,
            "aipf": outcome.ai_predicted_financial,
            "acti": outcome.actual_impact,
            "actf": outcome.actual_financial,
            "asc": outcome.accuracy_score,
            "afb": outcome.accuracy_feedback,
            "ttd": outcome.time_to_decision,
            "pl": outcome.prevented_loss,
            "now": now,
        },
    )
    db.commit()
    return {"status": "ok"}


@router.get("/decision-history")
def get_decision_history(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """获取 Decision History。"""
    rows = db.execute(
        text("""
            SELECT d.id, d.title, d.level, d.score,
                   d.source, d.confidence,
                   o.accuracy_score, o.actual_impact, o.prevented_loss,
                   d.created_at, d.decided_at
            FROM decisions d
            LEFT JOIN decision_outcomes o ON o.decision_id = d.id
            WHERE d.status IN ('executed', 'dismissed', 'rejected')
            ORDER BY d.decided_at DESC NULLS LAST
            LIMIT :lim
        """),
        {"lim": limit},
    ).fetchall()
    return [
        {
            "id": r.id,
            "title": r.title,
            "level": r.level,
            "score": r.score,
            "source": r.source,
            "accuracy_score": r.accuracy_score,
            "actual_impact": r.actual_impact,
            "prevented_loss": r.prevented_loss,
            "created_at": str(r.created_at) if r.created_at else "",
            "decided_at": str(r.decided_at) if r.decided_at else "",
        }
        for r in rows
    ]
```

在 `api/main.py` 注册：

```python
from api.routers.decision_history import router as history_router
app.include_router(history_router)
```

---

## Phase 5 完成检查清单

- [ ] AI Context Strip 在所有业务页面展示
- [ ] Cmd+K 打开命令面板，可搜索导航
- [ ] ESC 关闭面板 / 点击遮罩关闭
- [ ] Decision History API 返回已完成决策的追踪记录
- [ ] 自动推送机制每 5 分钟检查一次风险数据
- [ ] 提交 commit: `feat: Phase 5 — AI 神经系统集成`
