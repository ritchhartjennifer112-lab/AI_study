# api/services/event_service.py
"""Event 管道 — 接收事件 → 写入 DB → 调用 Priority Engine → 写入结果。"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from api.models.event import EventCreate, EventModel, EventResponse
from api.models.decision import DecisionCreate, DecisionModel, DecisionActionModel
from api.models.insight import InsightModel
from api.models.notification import NotificationModel
from api.domain.priority_engine import PriorityEngine

logger = logging.getLogger("event_service")


class EventService:
    """事件处理服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.engine = PriorityEngine()

    def process_event(self, event_data: EventCreate) -> dict:
        """接收、持久化、处理事件。"""

        # 1. 运行 Priority Engine
        result = self.engine.process(event_data)

        # 2. 持久化 Event
        event_record = EventModel(
            id=result.event_id,
            type=event_data.type,
            entity_type=event_data.entity_type,
            entity_id=event_data.entity_id,
            title=event_data.title,
            description=event_data.description,
            source=event_data.source,
            confidence=event_data.confidence,
            timestamp=event_data.timestamp,
            received_at=datetime.utcnow(),
            metadata_json=json.dumps(event_data.metadata, ensure_ascii=False),
            impact_score=result.score,
            urgency="high" if result.level >= 4 else "medium" if result.level >= 2 else "low",
        )
        self.db.add(event_record)

        decision_ids = []
        insight_ids = []

        # 3. 持久化 Decision（如果有）
        for dec in result.decisions:
            decision_id = f"dec_{datetime.utcnow().strftime('%Y%m%d')}_{id(dec) % 10000:04d}"
            dec_model = DecisionModel(
                id=decision_id,
                event_id=result.event_id,
                level=dec.level,
                score=dec.score,
                title=dec.title,
                description=dec.description,
                status=dec.status,
                source=dec.source,
                confidence=dec.confidence,
                roles=json.dumps(dec.roles, ensure_ascii=False),
                context_filter=dec.context_filter,
                created_at=datetime.utcnow(),
                expires_at=dec.expires_at,
            )
            self.db.add(dec_model)
            decision_ids.append(decision_id)

            # 持久化 Action
            for i, action in enumerate(dec.suggested_actions):
                action_model = DecisionActionModel(
                    id=f"act_{decision_id}_{i:02d}",
                    decision_id=decision_id,
                    action=action.action,
                    label=action.label,
                    description=action.description,
                    payload=json.dumps(action.payload, ensure_ascii=False),
                    confirmation_required=int(action.confirmation_required),
                    allowed_roles=json.dumps(action.allowed_roles, ensure_ascii=False),
                    sort_order=action.sort_order,
                )
                self.db.add(action_model)

        # 4. 持久化 Insight（如果有）
        for ins in result.insights:
            ins_model = InsightModel(
                id=ins.id,
                event_id=result.event_id,
                level=ins.level,
                score=ins.score,
                confidence=ins.confidence,
                text=ins.text,
                context_filter=ins.context_filter,
                created_at=ins.created_at,
                expires_at=ins.expires_at,
            )
            self.db.add(ins_model)
            insight_ids.append(ins.id)

        # 5. 持久化 Notification
        for notif in result.notifications:
            notif_model = NotificationModel(
                id=f"notif_{result.event_id}_{id(notif) % 10000:04d}",
                event_id=result.event_id,
                decision_id=decision_ids[0] if decision_ids else None,
                insight_id=insight_ids[0] if insight_ids else None,
                channel=notif["channel"],
                target=notif["target"],
                display_text=notif["display_text"],
                display_level=notif["display_level"],
                display_score=notif["display_score"],
            )
            self.db.add(notif_model)

        self.db.commit()

        return {
            "event_id": result.event_id,
            "level": result.level,
            "score": result.score,
            "confidence": result.confidence,
            "decisions": decision_ids,
            "insights": insight_ids,
        }

    def auto_push_risks(self) -> list[str]:
        """从 core/delivery_risk.py 拉取风险事件并写入事件中心。"""
        from api.models.event import EventModel

        pushed_ids: list[str] = []
        try:
            from core.delivery_risk import calc_all_risks

            risks = calc_all_risks()

            for risk in risks[:10]:
                event_id = f"risk_{risk['order_id']}_{datetime.utcnow().strftime('%Y%m%d')}"
                existing = (
                    self.db.query(EventModel)
                    .filter(EventModel.id == event_id)
                    .first()
                )
                if existing:
                    continue

                level = risk.get("risk_level", "绿")
                confidence_map = {"紫": 0.95, "红": 0.90, "黄": 0.75, "绿": 0.30, "灰": 0.10}
                event_data = EventCreate(
                    type="delay",
                    entity_type="work_order",
                    entity_id=risk["order_id"],
                    title=f"[{level}] {risk.get('risk_label', '交期风险')} — {risk['order_id']}",
                    description=risk.get("risk_reason", ""),
                    source="erp_sync",
                    confidence=confidence_map.get(level, 0.5),
                    timestamp=datetime.utcnow(),
                    metadata={
                        "risk_level": level,
                        "days_remaining": risk.get("days_remaining"),
                        "risk_label": risk.get("risk_label", ""),
                    },
                )
                self.process_event(event_data)
                pushed_ids.append(event_id)

        except Exception:
            logger.exception("auto_push_risks failed (delivery_risk)")
            pass

        # 生产风险
        try:
            from core.production_risk import calculate_all_risks

            for risk in calculate_all_risks()[:5]:
                event_id = f"prodrisk_{risk.get('order_id', '')}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
                existing = self.db.query(EventModel).filter(EventModel.id == event_id).first()
                if existing:
                    continue
                event_data = EventCreate(
                    type="delay",
                    entity_type="work_order",
                    entity_id=risk.get("order_id", ""),
                    title=f"生产风险 — {risk.get('order_id', '')}: {risk.get('risk_color', '')}",
                    description=risk.get("risk_reason", str(risk)),
                    source="erp_sync",
                    confidence=0.80,
                    timestamp=datetime.utcnow(),
                    metadata={"risk_type": "production", **{k: v for k, v in risk.items() if v is not None}},
                )
                self.process_event(event_data)
                pushed_ids.append(event_id)
        except Exception:
            logger.exception("auto_push_risks failed (production_risk)")

        # 技能缺口
        try:
            from core.skill_matrix import get_risk_devices

            for device in get_risk_devices()[:5]:
                event_id = f"skillgap_{device.get('device', '')}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
                existing = self.db.query(EventModel).filter(EventModel.id == event_id).first()
                if existing:
                    continue
                event_data = EventCreate(
                    type="personnel_change",
                    entity_type="equipment",
                    entity_id=device.get("device", ""),
                    title=f"技能缺口: {device.get('device', '')} 可操作人员不足",
                    description=f"设备 {device.get('device', '')} 仅有 {device.get('employee_count', 0)} 名可操作人员",
                    source="erp_sync",
                    confidence=0.85,
                    timestamp=datetime.utcnow(),
                    metadata={"risk_type": "skill_gap", **{k: v for k, v in device.items() if v is not None}},
                )
                self.process_event(event_data)
                pushed_ids.append(event_id)
        except Exception:
            logger.exception("auto_push_risks failed (skill_matrix)")

        # 派工瓶颈
        try:
            from core.dispatch_suggester import get_skill_risks

            for sr in get_skill_risks()[:5]:
                device_name = sr.get("device", sr.get("设备", ""))
                event_id = f"dispatch_{device_name}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
                existing = self.db.query(EventModel).filter(EventModel.id == event_id).first()
                if existing:
                    continue
                event_data = EventCreate(
                    type="personnel_change",
                    entity_type="equipment",
                    entity_id=str(device_name),
                    title=f"派工瓶颈: {device_name}",
                    description=str(sr),
                    source="erp_sync",
                    confidence=0.80,
                    timestamp=datetime.utcnow(),
                    metadata={"risk_type": "dispatch_bottleneck", **{k: v for k, v in sr.items() if v is not None}},
                )
                self.process_event(event_data)
                pushed_ids.append(event_id)
        except Exception:
            logger.exception("auto_push_risks failed (dispatch_suggester)")

        return pushed_ids
