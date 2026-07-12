# api/models/insight.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import Column, String, Float, Text, DateTime, Integer
from api.database import Base


class InsightModel(Base):
    __tablename__ = "insights"

    id = Column(String(32), primary_key=True)
    event_id = Column(String(32), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    text = Column(String(256), nullable=False)
    context_filter = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class InsightResponse(BaseModel):
    id: str
    event_id: str
    level: int
    score: float
    confidence: float
    text: str
    context_filter: str
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
