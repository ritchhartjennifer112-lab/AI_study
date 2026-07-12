# api/services/decision_service.py
"""Decision CRUD + Action 执行。"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from api.models.decision import DecisionModel, DecisionActionModel
from api.models.decision import DecisionResponse
from api.domain.context_filter import UserContext, filter_decisions


class DecisionService:
    """决策管理服务。"""

    def __init__(self, db: Session):
        self.db = db

    def get_decisions(
        self,
        context: UserContext,
        level_min: int = 1,
        status: str | None = "pending",
    ) -> list[dict]:
        """获取过滤后的决策列表。"""
        query = self.db.query(DecisionModel)

        if status:
            query = query.filter(DecisionModel.status == status)

        if level_min > 1:
            query = query.filter(DecisionModel.level >= level_min)

        rows = query.order_by(
            DecisionModel.level.desc(),
            DecisionModel.score.desc(),
        ).all()

        decisions = []
        for row in rows:
            actions = self.db.query(DecisionActionModel).filter(
                DecisionActionModel.decision_id == row.id
            ).order_by(DecisionActionModel.sort_order).all()

            decisions.append({
                "id": row.id,
                "event_id": row.event_id,
                "level": row.level,
                "score": row.score,
                "title": row.title,
                "description": row.description or "",
                "status": row.status,
                "source": row.source,
                "confidence": row.confidence,
                "roles": json.loads(row.roles or "[]"),
                "context_filter": row.context_filter or "",
                "suggested_actions": [
                    {
                        "action": a.action,
                        "label": a.label,
                        "description": a.description,
                        "payload": json.loads(a.payload or "{}"),
                        "confirmation_required": bool(a.confirmation_required),
                    }
                    for a in actions
                ],
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            })

        return filter_decisions(decisions, context, level_min, status)

    def execute_action(
        self,
        decision_id: str,
        action: str,
        idempotency_key: str,
        user: str = "",
        note: str = "",
        payload: dict | None = None,
    ) -> dict:
        """执行 Decision Action。

        幂等性：检查 idempotency_key，重复请求返回原结果。
        """
        # 查找 Decision
        dec = self.db.query(DecisionModel).filter(
            DecisionModel.id == decision_id
        ).first()
        if not dec:
            raise ValueError(f"Decision not found: {decision_id}")

        # 幂等检查
        if dec.idempotency_key == idempotency_key:
            return {
                "success": True,
                "decision_status": dec.status,
                "is_idempotent_replay": True,
                "message": "已处理过的请求（幂等重放）",
            }

        if action == "dismiss":
            dec.status = "dismissed"
        elif action == "approve_purchase":
            dec.status = "executing"
        elif action == "approve_expedite":
            dec.status = "executing"
        elif action == "dispatch_worker":
            dec.status = "approved"
        else:
            dec.status = "approved"

        dec.decided_at = datetime.utcnow()
        dec.decided_by = user or "unknown"
        dec.decision_note = note or ""
        dec.idempotency_key = idempotency_key

        self.db.commit()

        # Phase 7c: 如果 Decision 状态变为 approved/executing，且 payload 包含 ActionPlan，执行它
        action_plan_data = (payload or {}).get("action_plan")
        outcome_id = ""
        compensated = 0
        if dec.status in ("approved", "executing") and action_plan_data:
            try:
                from api.services.action_executor import ActionExecutor
                from core.agent.action_plan import ActionPlan

                executor = ActionExecutor(self.db)
                plan = ActionPlan.from_payload(action_plan_data)
                result = executor.execute_plan(plan)

                if result.success:
                    dec.status = "executed"
                else:
                    dec.status = "failed"
                    if result.compensated_steps > 0:
                        dec.decision_note = (dec.decision_note or "") + \
                            f" [已补偿 {result.compensated_steps} 步]"

                self.db.commit()
                outcome_id = result.outcome_id
                compensated = result.compensated_steps
            except Exception as e:
                import logging
                logging.getLogger('decision_service').error(
                    f"ActionExecutor 执行失败: decision={decision_id}, error={e}"
                )
                dec.status = "failed"
                dec.decision_note = (dec.decision_note or "") + f" [执行异常: {e}]"
                self.db.commit()

        return {
            "success": True,
            "decision_status": dec.status,
            "outcome_id": outcome_id,
            "compensated_steps": compensated,
            "message": f"决策 {decision_id} 已处理",
        }

    def get_decisions_for_role(self, role: str, page: str, level_min: int = 4) -> list[dict]:
        """按角色 + 页面获取决策（前端 API 调用入口）。"""
        context = UserContext(role=role, current_page=page)
        return self.get_decisions(context, level_min=level_min)

    @staticmethod
    def auto_expire_pending_decisions(db: Session) -> int:
        """批量过期 pending 决策（定时任务调用）。

        扫描所有 expires_at < now 且 status = 'pending' 的决策，
        将其置为 expired，完成状态图 pending → expired 闭环。

        调用方（APScheduler / Celery Beat）每小时执行一次：
            auto_expire_pending_decisions(next(get_db()))

        Returns:
            过期的决策数量
        """
        now = datetime.utcnow()
        expired = db.query(DecisionModel).filter(
            DecisionModel.expires_at.isnot(None),
            DecisionModel.expires_at < now,
            DecisionModel.status == "pending",
        ).all()
        count = len(expired)
        for dec in expired:
            dec.status = "expired"
            dec.resolved_at = now
        if count:
            db.commit()
        return count
