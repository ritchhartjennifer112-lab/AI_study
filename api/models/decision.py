# api/models/decision.py
"""Decision 数据模型 — ORM + Pydantic。"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, Text, DateTime, Integer, Index
from api.database import Base

VALID_STATUSES = {"pending", "approved", "rejected", "dismissed", "executing", "executed", "failed", "expired"}


class DecisionActionModel(Base):
    """Action 独立表（替代 JSON 字段）。"""
    __tablename__ = "decision_actions"

    id = Column(String(32), primary_key=True)
    decision_id = Column(String(32), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    label = Column(String(64), nullable=False)
    description = Column(Text, default="")
    payload = Column(Text, default="{}")  # JSON
    confirmation_required = Column(Integer, default=0)
    allowed_roles = Column(Text, default="[]")  # JSON array
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionModel(Base):
    __tablename__ = "decisions"

    id = Column(String(32), primary_key=True)
    event_id = Column(String(32), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    status = Column(String(16), nullable=False, default="pending", index=True)
    source = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    roles = Column(Text, default="[]")  # JSON array
    context_filter = Column(String(32), default="")
    idempotency_key = Column(String(64), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(String(32), nullable=True)
    decision_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_decisions_idempotency", idempotency_key, unique=True, sqlite_where=idempotency_key.isnot(None)),
    )


# ── Pydantic ──

class ActionCreate(BaseModel):
    action: str
    label: str
    description: str = ""
    payload: dict = {}
    confirmation_required: bool = False
    allowed_roles: list[str] = []
    sort_order: int = 0


class DecisionCreate(BaseModel):
    event_id: str
    level: int = Field(..., ge=1, le=5)
    score: float = Field(..., ge=0, le=100)
    title: str
    description: str = ""
    status: str = "pending"
    source: str
    confidence: float = 1.0
    roles: list[str] = []
    context_filter: str = ""
    suggested_actions: list[ActionCreate] = []
    expires_at: datetime | None = None


class DecisionResponse(BaseModel):
    id: str
    event_id: str
    level: int
    score: float
    title: str
    description: str
    status: str
    source: str
    confidence: float
    roles: list[str]
    context_filter: str
    suggested_actions: list[dict] = []
    created_at: datetime
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None

    model_config = {"from_attributes": True}
