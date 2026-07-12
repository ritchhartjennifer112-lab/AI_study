# api/domain/priority_engine.py
"""Factory Intelligence Priority Engine — 纯规则引擎，L1-L5 分级评分。

核心流程:
  1. 接收 RawEvent
  2. 调用 core/ontology_engine.py 追溯影响范围
  3. 计算 base_score（加权求和）
  4. 应用置信度覆写（高危事件有下限）
  5. 计算 final_score → level
  6. 产出 Decision / Insight / Notification
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field

from api.models.event import EventCreate, EventResponse
from api.models.decision import DecisionCreate, ActionCreate
from api.models.insight import InsightResponse


# ── 置信度下限覆写（DataModel §7.5）──
# 高危事件即使来自不确信的来源，也不能被"乘法漏斗"埋没
CONFIDENCE_FLOOR_OVERRIDE: dict[str, float] = {
    "breakdown": 0.90,   # 设备故障：置信度再低也要当回事
    "delay": 0.85,       # 交期延期：宁可信其有
    "quality": 0.80,     # 质量异常：底线
    "shortage": 0.75,    # 缺料：中等敏感
    # absent, overtime, personnel_change, schedule_change, purchase, maintenance 不设下限
}

# 高危类型 + 高影响 → 强制最低等级
FORCED_MIN_LEVEL_THRESHOLD: dict[str, dict] = {
    "breakdown": {"min_base_score": 70, "min_level": 4},
    "delay": {"min_base_score": 80, "min_level": 4},
}

# 低 confidence 不产生 L4-L5 Decision
LOW_CONFIDENCE_MAX_LEVEL: float = 0.70

# 影响维度权重（DataModel §7.1）
WEIGHT_DELIVERY = 0.40
WEIGHT_FINANCIAL = 0.30
WEIGHT_CUSTOMER = 0.20
WEIGHT_ANOMALY = 0.10


@dataclass
class Impact:
    """Ontology 追溯结果。"""
    entity: str            # "A线", "WO-1827"
    entity_type: str       # "production_line", "work_order"
    effect: str            # "缺少冲压工", "产能下降5%"
    economic_loss: float = 0.0


@dataclass
class EngineResult:
    """Priority Engine 处理结果。"""
    event_id: str
    level: int
    score: float
    confidence: float
    source: str
    impacts: list[Impact] = field(default_factory=list)
    decisions: list[DecisionCreate] = field(default_factory=list)
    insights: list[InsightResponse] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)


class PriorityEngine:
    """消息价值评估引擎。不是 AI，是完全确定性的加权评分系统。"""

    def __init__(self):
        self._ontology = None
        self._ontology_path = None

    def _get_ontology(self):
        """Lazy-init ontology engine. Returns None if unavailable."""
        if self._ontology is None:
            from pathlib import Path
            from api.config import BASE_DIR
            path = Path(BASE_DIR) / "config" / "ontology.json"
            if path.exists():
                try:
                    from core.ontology_engine import OntologyEngine
                    self._ontology = OntologyEngine(str(path))
                    self._ontology_path = str(path)
                except Exception:
                    pass
        return self._ontology

    def process(self, event: EventCreate) -> EngineResult:
        """处理一个原始事件，返回分级评分后的结果。"""

        # Step 1: 通过 ontology 追溯影响范围
        impacts = self._trace_impacts(event)

        # Step 2: 计算基础分数
        base_score = self._calc_base_score(event, impacts)

        # Step 3: 应用置信度覆写（DataModel §7.5）
        effective_confidence, final_level, final_score = self._apply_confidence(
            event_type=event.type,
            base_score=base_score,
            raw_confidence=event.confidence,
        )

        # Step 4: 生成 Event ID
        event_id = self._gen_id("evt")

        result = EngineResult(
            event_id=event_id,
            level=final_level,
            score=final_score,
            confidence=effective_confidence,
            source=event.source,
            impacts=impacts,
        )

        # Step 5: 根据级别分发
        if final_level >= 4:
            # L4-L5 → Decision
            decision = self._build_decision(event_id, event, final_level, final_score, impacts)
            result.decisions.append(decision)
            result.notifications.append({
                "channel": "decision_center",
                "target": ",".join(decision.roles),
                "display_text": decision.title,
                "display_level": final_level,
                "display_score": final_score,
            })
        elif final_level >= 2:
            # L2-L3 → Insight + Context Strip
            insight = self._build_insight(event_id, event, final_level, final_score, impacts)
            result.insights.append(insight)
            result.notifications.append({
                "channel": "context_strip",
                "target": self._infer_context_filter(event),
                "display_text": insight.text,
                "display_level": final_level,
                "display_score": final_score,
            })

        # L1 → 只记录 notification（data_log channel）
        result.notifications.append({
            "channel": "data_log",
            "target": "",
            "display_text": event.title,
            "display_level": final_level,
            "display_score": final_score,
        })

        return result

    def _trace_impacts(self, event: EventCreate) -> list[Impact]:
        """通过 ontology 引擎追溯影响。"""
        onto = self._get_ontology()
        if onto is None:
            return []
        try:
            # Map entity_type to the ontology's expected object name
            type_map = {
                "work_order": "WorkOrder",
                "employee": "Worker",
                "equipment": "Equipment",
                "material": "Material",
            }
            start_object = type_map.get(event.entity_type, "WorkOrder")
            raw = onto.trace_causality(start_object, event.entity_id, pg_engine=None)
            impacts = []
            for item in (raw or []):
                if isinstance(item, dict):
                    impacts.append(Impact(
                        entity=item.get("id", ""),
                        entity_type=item.get("node_type", "unknown").lower(),
                        effect=f"hop_{item.get('hop_count', 0)}",
                    ))
            return impacts
        except Exception:
            return []

    def _calc_base_score(self, event: EventCreate, impacts: list[Impact]) -> float:
        """计算基础分数（加权求和，DataModel §7.1）。

        各维度评分逻辑会根据事件类型和影响范围自动推断。
        Phase 1 使用简化的确定性规则，后续可配置化。
        """
        # delivery_impact: 基于影响数量和类型
        has_order_impact = any(i.entity_type == "work_order" for i in impacts)
        has_line_impact = any(i.entity_type == "production_line" for i in impacts)
        num_impacts = len(impacts)

        if event.type in ("delay",):
            delivery = 100
        elif event.type in ("breakdown",):
            delivery = 90
        elif event.type in ("shortage",):
            delivery = 60
        else:
            delivery = min(30 + num_impacts * 10, 100)

        # financial_impact: 基于事件类型估算
        financial_map = {
            "delay": 75, "breakdown": 80, "shortage": 50,
            "quality": 60, "absent": 50, "overtime": 20,
            "purchase": 30, "maintenance": 20,
        }
        financial = financial_map.get(event.type, 20)

        # customer_tier: 默认为重要
        customer = 50

        # anomaly_level
        anomaly_map = {
            "delay": 80, "breakdown": 80, "quality": 60,
            "shortage": 60, "absent": 30,
        }
        anomaly = anomaly_map.get(event.type, 10)

        score = (
            delivery * WEIGHT_DELIVERY
            + financial * WEIGHT_FINANCIAL
            + customer * WEIGHT_CUSTOMER
            + anomaly * WEIGHT_ANOMALY
        )
        return round(score, 1)

    def _apply_confidence(
        self, event_type: str, base_score: float, raw_confidence: float
    ) -> tuple[float, int, float]:
        """应用置信度覆写（DataModel §7.5）。

        Returns:
            (effective_confidence, final_level, final_score)
        """
        # Step 1: 类型覆写 — 高危事件有 confidence 下限
        floor = CONFIDENCE_FLOOR_OVERRIDE.get(event_type, 0.0)
        effective_confidence = max(raw_confidence, floor)

        # Step 2: score 调整
        final_score = round(base_score * effective_confidence)

        # Step 3: level 判定
        level = self._score_to_level(final_score)

        # Step 4: 天花板突破 — 置信度覆写事件若 base_score 已达 L5 但乘法降级丢等级
        if event_type in CONFIDENCE_FLOOR_OVERRIDE and base_score >= 95:
            # 灾难性事件（如恶性故障 base_score=100）：强制保留 L5
            level = max(level, 5)
            final_score = max(final_score, 91)

        # Step 5: 高危 + 高影响 → 强制置顶
        threshold = FORCED_MIN_LEVEL_THRESHOLD.get(event_type)
        if threshold and base_score >= threshold["min_base_score"]:
            level = max(level, threshold["min_level"])
            final_score = max(final_score, 76)

        # Step 6: 低 confidence 不产生 L4-L5（用 effective_confidence 判断，
        # 保证已被置信度覆写抬高的高危事件不被再次压低）
        if effective_confidence < LOW_CONFIDENCE_MAX_LEVEL:
            level = min(level, 3)

        return effective_confidence, level, final_score

    def _score_to_level(self, score: float) -> int:
        """分数 → L1-L5。"""
        if score <= 20:
            return 1
        elif score <= 50:
            return 2
        elif score <= 75:
            return 3
        elif score <= 90:
            return 4
        else:
            return 5

    def _build_decision(
        self, event_id: str, event: EventCreate,
        level: int, score: float, impacts: list[Impact],
    ) -> DecisionCreate:
        """构建 Decision 对象。"""
        actions = self._suggest_actions(event, impacts)

        # 默认决策角色
        roles = ["supervisor"]
        if level >= 5:
            roles = ["admin", "supervisor"]
        elif level >= 4:
            roles = ["supervisor", "admin"]

        return DecisionCreate(
            event_id=event_id,
            level=level,
            score=score,
            title=event.title,
            description=event.description or self._build_description(event, impacts),
            status="pending",
            source=event.source,
            confidence=event.confidence,
            roles=roles,
            context_filter=self._infer_context_filter(event),
            suggested_actions=actions,
            expires_at=datetime.utcnow() + timedelta(days=3),
        )

    def _suggest_actions(self, event: EventCreate, impacts: list[Impact]) -> list[ActionCreate]:
        """根据事件类型推荐操作。"""
        actions = [
            ActionCreate(action="dismiss", label="忽略", confirmation_required=True),
            ActionCreate(action="view_detail", label="查看详情"),
        ]

        if event.type == "delay":
            actions.insert(0, ActionCreate(
                action="approve_expedite", label="批准加急",
                payload={"order_id": event.entity_id},
            ))
            actions.insert(1, ActionCreate(
                action="reschedule", label="调整排产",
                payload={"order_id": event.entity_id},
            ))
        elif event.type == "shortage":
            actions.insert(0, ActionCreate(
                action="approve_purchase", label="批准采购",
            ))
        elif event.type == "absent":
            actions.insert(0, ActionCreate(
                action="dispatch_worker", label="调配人员",
                confirmation_required=True,
            ))
        elif event.type == "breakdown":
            actions.insert(0, ActionCreate(
                action="dispatch_worker", label="安排维修",
                confirmation_required=True,
            ))
        elif event.type == "overtime":
            actions.insert(0, ActionCreate(
                action="approve_overtime", label="批准加班",
            ))

        return actions

    def _build_insight(
        self, event_id: str, event: EventCreate,
        level: int, score: float, impacts: list[Impact],
    ) -> InsightResponse:
        """构建 Insight 对象。"""
        parts = []
        if impacts:
            main = impacts[0]
            parts.append(f"{main.entity}{main.effect}")
        else:
            parts.append(event.title)

        text = " · ".join(parts)
        if len(text) > 80:
            text = text[:77] + "..."

        return InsightResponse(
            id=self._gen_id("ins"),
            event_id=event_id,
            level=level,
            score=score,
            confidence=event.confidence,
            text=text,
            context_filter=self._infer_context_filter(event),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )

    def _build_description(self, event: EventCreate, impacts: list[Impact]) -> str:
        parts = [f"来源: {event.source}"]
        if impacts:
            parts.append(f"影响: {'; '.join(f'{i.entity}{i.effect}' for i in impacts)}")
        return " · ".join(parts)

    def _infer_context_filter(self, event: EventCreate) -> str:
        """根据事件类型推断语境过滤器。"""
        type_to_context = {
            "absent": "personnel",
            "personnel_change": "personnel",
            "breakdown": "equipment",
            "maintenance": "equipment",
            "shortage": "materials",
            "delay": "production",
            "schedule_change": "production",
            "quality": "production",
            "purchase": "materials",
            "overtime": "personnel",
        }
        return type_to_context.get(event.type, "production")

    def _gen_id(self, prefix: str) -> str:
        """生成唯一 ID: {prefix}_{yyyymmdd}_{seq}"""
        now = datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        seq = id(now) % 10000  # 简单序列，生产环境用雪花算法
        return f"{prefix}_{date_str}_{seq:04d}"
