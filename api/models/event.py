# api/models/event.py
"""Event 数据模型 — ORM + Pydantic。"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, Float, Text, DateTime, Integer
from api.database import Base


# ── ORM Model ──

class EventModel(Base):
    __tablename__ = "events"

    id = Column(String(32), primary_key=True)
    type = Column(String(32), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    source = Column(String(32), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=1.0)
    timestamp = Column(DateTime, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json = Column(Text, default="{}")  # JSON string
    impact_score = Column(Float, nullable=True)
    urgency = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Pydantic Schemas ──

VALID_EVENT_TYPES = {
    "absent", "shortage", "delay", "breakdown", "quality",
    "overtime", "purchase", "personnel_change", "schedule_change", "maintenance",
}

VALID_SOURCES = {
    "erp_sync", "excel_import", "inbox_ai", "agent_inference", "manual",
}


class EventCreate(BaseModel):
    """创建事件的请求体。"""
    type: str = Field(..., description="事件类型")
    entity_type: str = Field(..., description="实体类型")
    entity_id: str = Field(..., description="实体标识")
    title: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    source: str = Field(..., description="事件来源")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime
    metadata: dict = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event type: {v}. Must be one of {VALID_EVENT_TYPES}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {v}. Must be one of {VALID_SOURCES}")
        return v

    @field_validator("timestamp")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        # 允许 30 秒时钟偏差（工厂内各服务器时间可能不完全同步）
        now = datetime.utcnow()
        v_naive = v.replace(tzinfo=None) if v.tzinfo else v
        if v_naive > now + timedelta(seconds=30):
            raise ValueError("Event timestamp cannot be in the future (allow 30s clock skew)")
        return v


class EventResponse(BaseModel):
    """事件响应（不包含内部字段）。"""
    id: str
    type: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    source: str
    confidence: float
    timestamp: datetime
    received_at: datetime
    impact_score: float | None = None
    urgency: str | None = None
    metadata: dict = {}

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, model: EventModel) -> "EventResponse":
        import json
        return cls(
            id=model.id,
            type=model.type,
            entity_type=model.entity_type,
            entity_id=model.entity_id,
            title=model.title,
            description=model.description or "",
            source=model.source,
            confidence=model.confidence,
            timestamp=model.timestamp,
            received_at=model.received_at,
            impact_score=model.impact_score,
            urgency=model.urgency,
            metadata=json.loads(model.metadata_json or "{}"),
        )
