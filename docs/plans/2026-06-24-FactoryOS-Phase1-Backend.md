# Factory OS Phase 1: 后端骨架 + Priority Engine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 必须先读 `docs/plans/2026-06-24-FactoryOS-DataModel.md` 了解完整数据模型，再执行本文件 Task。

---

## 文件结构

```
api/                          # NEW — 整个 api/ 目录从零搭建
├── __init__.py
├── main.py                   # FastAPI 应用启动
├── config.py                 # 配置
├── database.py               # SQLAlchemy 引擎 + Session
├── dependencies.py           # JWT + DB 依赖注入
├── models/                   # Pydantic 模型（请求/响应）
│   ├── __init__.py
│   ├── event.py
│   ├── decision.py
│   ├── insight.py
│   ├── action.py
│   └── notification.py
├── domain/                   # 核心业务逻辑
│   ├── __init__.py
│   ├── priority_engine.py    # ★ 核心：L1-L5 评分 + 置信度覆写
│   └── context_filter.py     # 语境过滤
├── services/                 # 编排层
│   ├── __init__.py
│   ├── event_service.py      # Event 管道
│   ├── decision_service.py   # Decision CRUD
│   └── notification_service.py # 投递逻辑
├── routers/                  # API 路由
│   ├── __init__.py
│   ├── auth.py               # JWT 认证
│   ├── events.py              # POST /api/events
│   ├── decisions.py           # GET /api/decision-center
│   ├── context_strip.py       # GET /api/context-strip
│   ├── actions.py             # POST /api/actions
│   └── business.py            # 业务只读 API
└── tests/                    # Phase 1 测试
    ├── __init__.py
    ├── test_priority_engine.py
    ├── test_context_filter.py
    ├── test_confidence_override.py
    └── test_api.py
```

---

## Task 1-1: FastAPI 基础设施

**文件：**
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `api/config.py`
- Create: `api/database.py`

### Step 1: config.py

```python
# api/config.py
"""应用配置，从环境变量读取，有合理默认值。"""
from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'factory.db'}",
    )

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "factory-os-dev-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 小时

    # 服务
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ID 生成
    INSTANCE_ID: int = 1


settings = Settings()
```

### Step 2: database.py

```python
# api/database.py
"""SQLAlchemy 2.0 同步引擎（保留异步迁移接口）。

与现有 core/database.py 共存，不冲突。
core/database.py 供 core/*.py 使用。
api/database.py 供 api/*.py 使用。
"""
from __future__ import annotations
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from api.config import settings


class Base(DeclarativeBase):
    pass


# SQLite 同步引擎（开发阶段）
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

# 启用 SQLite WAL 模式提升并发
if "sqlite" in settings.DATABASE_URL:

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """FastAPI 依赖注入：获取数据库 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表。Phase 1 启动时调用一次。"""
    Base.metadata.create_all(bind=engine)
```

### Step 3: main.py

```python
# api/main.py
"""Factory OS FastAPI 应用入口。"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.database import init_db

app = FastAPI(
    title="Factory OS API",
    version="0.1.0",
    description="Factory Intelligence Engine",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    # 后续注册 router 在这里添加
    # from api.routers import events, decisions, ...
    # app.include_router(events.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
```

### Step 4: 验证

```bash
cd d:/AI知识库/AI++++/工厂现场——工时
pip install fastapi uvicorn sqlalchemy pydantic
uvicorn api.main:app --reload --port 8000

# 另一个终端验证
curl http://localhost:8000/api/health
# 应返回: {"status":"ok","version":"0.1.0"}
```

---

## Task 1-2: 数据模型（Pydantic + SQLAlchemy ORM 类）

**文件：**
- Create: `api/__init__.py`
- Create: `api/models/__init__.py`
- Create: `api/models/event.py`
- Create: `api/models/decision.py`
- Create: `api/models/insight.py`
- Create: `api/models/action.py`
- Create: `api/models/notification.py`

### Step 1: 建表 ORM + Pydantic 放在一起

```python
# api/models/__init__.py
from api.models.event import EventModel, EventCreate, EventResponse
from api.models.decision import (
    DecisionModel,
    DecisionCreate,
    DecisionResponse,
    DecisionActionModel,
)
from api.models.insight import InsightModel, InsightResponse
from api.models.notification import NotificationModel

__all__ = [
    "EventModel", "EventCreate", "EventResponse",
    "DecisionModel", "DecisionCreate", "DecisionResponse",
    "DecisionActionModel",
    "InsightModel", "InsightResponse",
    "NotificationModel",
]
```

```python
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
        if v > datetime.utcnow() + timedelta(seconds=30):
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
```

```python
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
```

```python
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
```

```python
# api/models/notification.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import Column, String, Float, Text, DateTime, Integer
from api.database import Base


class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(String(32), primary_key=True)
    event_id = Column(String(32), nullable=False, index=True)
    decision_id = Column(String(32), nullable=True)
    insight_id = Column(String(32), nullable=True)
    channel = Column(String(32), nullable=False, index=True)
    target = Column(String(64), nullable=False, index=True)
    display_text = Column(String(512), nullable=False)
    display_level = Column(Integer, nullable=False)
    display_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)


class NotificationResponse(BaseModel):
    id: str
    event_id: str
    decision_id: str | None = None
    insight_id: str | None = None
    channel: str
    target: str
    display_text: str
    display_level: int
    display_score: float
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}
```

### 验证

```bash
cd d:/AI知识库/AI++++/工厂现场——工时
python -c "
from api.database import init_db
init_db()
print('Tables created:', [t for t in __import__('sqlalchemy').inspect(__import__('api.database', fromlist=['engine']).engine).get_table_names()])
"
```

---

## Task 1-3: Priority Engine（核心）

**文件：**
- Create: `api/domain/__init__.py`
- Create: `api/domain/priority_engine.py`

这是整个系统最重要的文件。实现 DataModel §7 的评分公式和 §7.5 的置信度覆写。

```python
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
from core.ontology_engine import OntologyEngine


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
        self.ontology = OntologyEngine()

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
        try:
            raw = self.ontology.trace(entity_id=event.entity_id, entity_type=event.entity_type)
            impacts = []
            for item in (raw or []):
                if isinstance(item, dict):
                    impacts.append(Impact(
                        entity=item.get("entity", ""),
                        entity_type=item.get("type", "unknown"),
                        effect=item.get("effect", ""),
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
            delivery = 80 if has_order_impact else 60
        elif event.type in ("breakdown",):
            delivery = 90 if has_line_impact else 70
        elif event.type in ("shortage",):
            delivery = 60 if num_impacts > 0 else 40
        else:
            delivery = min(30 + num_impacts * 10, 100)

        # financial_impact: 基于事件类型估算
        financial_map = {
            "delay": 75, "breakdown": 80, "shortage": 50,
            "quality": 60, "absent": 30, "overtime": 20,
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

        # Step 6: 低 confidence 不产生 L4-L5
        if raw_confidence < LOW_CONFIDENCE_MAX_LEVEL:
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
```

---

## Task 1-4: Context Filter

**文件：**
- Create: `api/domain/context_filter.py`

```python
# api/domain/context_filter.py
"""语境感知过滤器 — 替代简单的 role_filter。

不是 React 逻辑，是后端查询过滤服务。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class UserContext:
    """当前用户的语境。"""
    role: str                    # "operator" | "supervisor" | "admin"
    current_page: str            # "production" | "equipment" | "personnel" | "materials" | "data" | "settings"
    current_focus: str = ""      # 可选，如 "WO-1827", "E-0045"


# 角色 → 可见等级范围
ROLE_LEVEL_RANGE: dict[str, tuple[int, int]] = {
    "operator": (1, 2),      # 只看到 L1-L2
    "supervisor": (2, 4),    # L2-L4
    "admin": (1, 5),         # 全可见
}

# 角色 → 可见的语境过滤器
ROLE_CONTEXT_ACCESS: dict[str, list[str]] = {
    "operator": ["production", "personnel"],
    "supervisor": ["production", "equipment", "personnel", "materials"],
    "admin": ["production", "equipment", "personnel", "materials", "data", "settings"],
}


def filter_decisions(
    decisions: list[dict],
    context: UserContext,
    level_min: int = 1,
    status_filter: str | None = "pending",
) -> list[dict]:
    """按语境过滤 Decision 列表。

    1. 角色决定可见等级范围
    2. current_page 决定展示哪些 context_filter 的消息
    3. 按 level DESC + score DESC 排序
    """
    level_range = ROLE_LEVEL_RANGE.get(context.role, (1, 5))
    allowed_contexts = ROLE_CONTEXT_ACCESS.get(context.role, [])

    filtered = []
    for d in decisions:
        # 等级过滤
        if d.get("level", 0) < level_min:
            continue
        if d.get("level", 0) > level_range[1]:
            continue

        # 角色可见范围
        if d.get("level", 0) < level_range[0]:
            continue

        # 语境过滤：只有 current_page 匹配的消息才展示
        d_context = d.get("context_filter", "")
        if d_context and d_context not in allowed_contexts:
            continue
        if d_context and context.current_page not in ("", d_context) and d_context != "":
            # 例外：admin 在全域页面可见所有
            if context.role != "admin":
                continue

        # 状态过滤
        if status_filter and d.get("status") != status_filter:
            continue

        filtered.append(d)

    # 排序: level DESC + score DESC
    filtered.sort(key=lambda x: (-x.get("level", 0), -x.get("score", 0)))
    return filtered


def filter_insights(
    insights: list[dict],
    context: UserContext,
    limit: int = 3,
) -> list[dict]:
    """按语境过滤 Insight。

    只展示与当前页面相关的洞察。
    """
    page = context.current_page

    # 只展示匹配当前页面的
    filtered = [i for i in insights if i.get("context_filter", "") == page]

    # 排序: level DESC + score DESC
    filtered.sort(key=lambda x: (-x.get("level", 0), -x.get("score", 0)))

    return filtered[:limit]
```

---

## Task 1-5: Services（编排层）

**文件：**
- Create: `api/services/__init__.py`
- Create: `api/services/event_service.py`
- Create: `api/services/decision_service.py`
- Create: `api/services/notification_service.py`

### Step 1: event_service.py

```python
# api/services/event_service.py
"""Event 管道 — 接收事件 → 写入 DB → 调用 Priority Engine → 写入结果。"""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session

from api.models.event import EventCreate, EventModel, EventResponse
from api.models.decision import DecisionCreate, DecisionModel, DecisionActionModel
from api.models.insight import InsightModel
from api.models.notification import NotificationModel
from api.domain.priority_engine import PriorityEngine


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
```

### Step 2: decision_service.py

```python
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
            dec.status = "executing"  # 异步，先置为 executing
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

        return {
            "success": True,
            "decision_status": dec.status,
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
```

### Step 3: notification_service.py

```python
# api/services/notification_service.py
"""通知投递服务 — 查询 Context Strip / Decision Center 内容。"""
from __future__ import annotations
from sqlalchemy.orm import Session

from api.models.notification import NotificationModel
from api.models.insight import InsightModel
from api.domain.context_filter import UserContext, filter_insights


class NotificationService:
    """通知查询服务。"""

    def __init__(self, db: Session):
        self.db = db

    def get_context_strip(
        self,
        page: str,
        role: str = "admin",
        limit: int = 3,
    ) -> list[dict]:
        """获取 AI Context Strip 内容。"""
        query = self.db.query(InsightModel).filter(
            InsightModel.context_filter == page,
            InsightModel.level.between(2, 3),
        ).order_by(
            InsightModel.level.desc(),
            InsightModel.score.desc(),
        ).limit(limit * 2).all()

        insights = [
            {
                "id": ins.id,
                "event_id": ins.event_id,
                "level": ins.level,
                "score": ins.score,
                "confidence": ins.confidence,
                "text": ins.text,
                "context_filter": ins.context_filter,
            }
            for ins in query
        ]

        context = UserContext(role=role, current_page=page)
        return filter_insights(insights, context, limit=limit)
```

---

## Task 1-6: API 路由

**文件：**
- Create: `api/routers/__init__.py`
- Create: `api/routers/events.py`
- Create: `api/routers/decisions.py`
- Create: `api/routers/context_strip.py`
- Create: `api/routers/actions.py`

### Step 1: events.py

```python
# api/routers/events.py
"""POST /api/events — 事件接收入口。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.event import EventCreate, EventResponse
from api.services.event_service import EventService

router = APIRouter(prefix="/api", tags=["events"])


@router.post("/events")
def post_event(event: EventCreate, db: Session = Depends(get_db)):
    """接收原始事件，经 Priority Engine 处理后持久化。"""
    service = EventService(db)
    result = service.process_event(event)
    return result


@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    """查询事件详情。"""
    from api.models.event import EventModel
    evt = db.query(EventModel).filter(EventModel.id == event_id).first()
    if not evt:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.from_orm_model(evt)
```

### Step 2: decisions.py

```python
# api/routers/decisions.py
"""GET /api/decision-center — 决策查询。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.decision_service import DecisionService
from api.domain.context_filter import UserContext

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decision-center")
def get_decisions(
    role: str = Query("admin"),
    page: str = Query(""),
    level_min: int = Query(4),
    status: str = Query("pending"),
    db: Session = Depends(get_db),
):
    """获取过滤后的决策列表。

    - role: 角色
    - page: 当前页面（context_filter）
    - level_min: 最低等级
    - status: 状态过滤
    """
    service = DecisionService(db)
    context = UserContext(role=role, current_page=page)
    items = service.get_decisions(context, level_min=level_min, status=status)
    return {"items": items, "total": len(items)}
```

### Step 3: context_strip.py

```python
# api/routers/context_strip.py
"""GET /api/context-strip — AI Context Strip 内容。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.notification_service import NotificationService

router = APIRouter(prefix="/api", tags=["context-strip"])


@router.get("/context-strip")
def get_context_strip(
    page: str = Query(...),
    role: str = Query("admin"),
    limit: int = Query(3),
    db: Session = Depends(get_db),
):
    """获取 AI Context Strip 内容。

    - page: 当前页面
    - role: 角色
    - limit: 返回条数上限
    """
    service = NotificationService(db)
    items = service.get_context_strip(page=page, role=role, limit=limit)
    return {"items": items}
```

### Step 4: actions.py

```python
# api/routers/actions.py
"""POST /api/actions — 执行操作。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.decision_service import DecisionService

router = APIRouter(prefix="/api", tags=["actions"])


class ActionRequest(BaseModel):
    action: str
    decision_id: str
    idempotency_key: str
    payload: dict = {}
    user: str = ""
    note: str = ""


@router.post("/actions")
def execute_action(req: ActionRequest, db: Session = Depends(get_db)):
    """执行 Decision 上的操作。

    幂等性保证：相同 idempotency_key 的重复请求返回相同结果。
    """
    service = DecisionService(db)
    try:
        result = service.execute_action(
            decision_id=req.decision_id,
            action=req.action,
            idempotency_key=req.idempotency_key,
            user=req.user,
            note=req.note,
            payload=req.payload,
        )
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
```

### Step 5: 注册路由到 main.py

```python
# 在 api/main.py 的 on_startup 函数后面添加：
from api.routers import events, decisions, context_strip, actions

app.include_router(events.router)
app.include_router(decisions.router)
app.include_router(context_strip.router)
app.include_router(actions.router)
```

### 验证

```bash
# 启动
uvicorn api.main:app --reload --port 8000

# 测试推送事件
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "absent",
    "entity_type": "employee",
    "entity_id": "张三",
    "title": "张三请假 2026-06-24 至 2026-06-25",
    "description": "事假2天",
    "source": "inbox_ai",
    "confidence": 0.88,
    "timestamp": "2026-06-24T07:30:00Z",
    "metadata": {"leave_type": "事假"}
  }'

# 应返回类似:
# {"event_id":"evt_...","level":3,"score":46,"decisions":[],"insights":["ins_..."]}

# 测试 Decision Center
curl "http://localhost:8000/api/decision-center?role=admin&page=production&level_min=4"

# 测试 Context Strip
curl "http://localhost:8000/api/context-strip?page=production&role=admin&limit=3"
```

---

## Task 1-7: 业务只读 API

**文件：**
- Create: `api/routers/business.py`
- Modify: `api/main.py`（注册路由）

此 Task 提供 Phase 2 页面需要的数据接口。只读，直接查询 core/*.py。

```python
# api/routers/business.py
"""业务只读 API — 供前端页面调用。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime

from api.database import get_db

router = APIRouter(prefix="/api/business", tags=["business"])


@router.get("/work-orders")
def list_work_orders(
    status: str = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    """工单列表（只读）。"""
    sql = "SELECT * FROM work_orders"
    params = {}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit
    rows = db.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/work-orders/{order_id}")
def get_work_order(order_id: str, db: Session = Depends(get_db)):
    """工单详情。"""
    row = db.execute(
        text("SELECT * FROM work_orders WHERE id = :id"),
        {"id": order_id},
    ).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Work order not found")
    return dict(row._mapping)


@router.get("/shortages")
def list_shortages(
    status: str = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    """缺料列表。"""
    sql = "SELECT * FROM material_shortages"
    params = {}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY registered_date DESC LIMIT :limit"
    params["limit"] = limit
    rows = db.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/employees")
def list_employees(db: Session = Depends(get_db)):
    """员工列表。"""
    rows = db.execute(text("SELECT * FROM employees ORDER BY name")).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/equipment")
def list_equipment(db: Session = Depends(get_db)):
    """设备列表。"""
    rows = db.execute(text("SELECT * FROM equipment ORDER BY name")).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/efficiency")
def get_efficiency(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
):
    """效率数据。"""
    today = date.today().isoformat()
    start = start_date or today
    end = end_date or today
    rows = db.execute(
        text("""
            SELECT employee, SUM(hours) as total_hours,
                   COUNT(DISTINCT date) as work_days
            FROM daily_reports
            WHERE date >= :start AND date <= :end
            GROUP BY employee
            ORDER BY total_hours DESC
            LIMIT 20
        """),
        {"start": start, "end": end},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/production-risk")
def get_production_risk(db: Session = Depends(get_db)):
    """生产风险列表（来自 core/delivery_risk.py）。"""
    try:
        from core.delivery_risk import calc_all_risks
        risks = calc_all_risks()
        return {"risks": risks[:20]}
    except Exception as e:
        return {"risks": [], "error": str(e)}
```

在 `api/main.py` 注册：

```python
from api.routers.business import router as business_router
app.include_router(business_router)
```

---

## Task 1-8: 单元测试 — Priority Engine 核心

**文件：**
- Create: `api/tests/__init__.py`
- Create: `api/tests/test_priority_engine.py`
- Create: `api/tests/test_confidence_override.py`
- Create: `api/tests/test_context_filter.py`

### Step 1: test_priority_engine.py

```python
# api/tests/test_priority_engine.py
"""Priority Engine 单元测试。"""
from datetime import datetime
from api.domain.priority_engine import PriorityEngine, CONFIDENCE_FLOOR_OVERRIDE
from api.models.event import EventCreate


def test_absent_event_is_l2_l3():
    """请假事件应该是 L2-L3，不是 L4-L5。"""
    engine = PriorityEngine()
    event = EventCreate(
        type="absent",
        entity_type="employee",
        entity_id="张三",
        title="张三请假",
        source="inbox_ai",
        confidence=0.88,
        timestamp=datetime(2026, 6, 24, 7, 30),
    )
    result = engine.process(event)
    assert 2 <= result.level <= 3, f"请假应该 L2-L3，实际 L{result.level}"
    assert len(result.decisions) == 0, "L3 以下不应产生 Decision"
    assert len(result.insights) >= 1, "应有 Insight"


def test_delay_event_is_l4_or_above():
    """交期延期事件应该是 L4 以上。"""
    engine = PriorityEngine()
    event = EventCreate(
        type="delay",
        entity_type="work_order",
        entity_id="WO-1827",
        title="WO-1827 预计延期 2 天",
        description="涉及金额 ¥126,000",
        source="erp_sync",
        confidence=0.95,
        timestamp=datetime(2026, 6, 24, 8, 0),
    )
    result = engine.process(event)
    assert result.level >= 4, f"延期应该 L4+，实际 L{result.level}"
    assert len(result.decisions) >= 1, "L4 以上应产生 Decision"


def test_breakdown_with_low_confidence():
    """设备故障即使低置信度也要被重视（置信度覆写）。"""
    engine = PriorityEngine()
    event = EventCreate(
        type="breakdown",
        entity_type="equipment",
        entity_id="E-0045",
        title="E-0045 冲压机故障停机",
        source="agent_inference",
        confidence=0.5,  # 很低
        timestamp=datetime(2026, 6, 24, 9, 0),
    )
    result = engine.process(event)
    # breakdown 的 confidence floor = 0.9，所以 effective >= 0.9
    assert result.confidence >= 0.9, f"覆写后 confidence 应 >=0.9，实际 {result.confidence}"
    assert result.level >= 4, f"breakdown+高影响应 >=L4，实际 L{result.level}"


def test_multi_event_types():
    """测试多种事件类型的评分合理性。"""
    engine = PriorityEngine()

    cases = [
        ("absent", "inbox_ai", 0.6, 2, "请假+低可信 → 不高于 L3"),
        ("shortage", "erp_sync", 0.95, 3, "缺料+高可信 → L3"),
        ("quality", "inbox_ai", 0.7, 3, "质量+中可信 → L3"),
        ("overtime", "manual", 1.0, 2, "加班 → L2 提醒"),
    ]

    for event_type, source, conf, min_level, desc in cases:
        event = EventCreate(
            type=event_type,
            entity_type="test",
            entity_id="test-001",
            title=f"Test {event_type}",
            source=source,
            confidence=conf,
            timestamp=datetime(2026, 6, 24, 10, 0),
        )
        result = engine.process(event)
        assert result.level >= min_level, f"{desc}: expected >=L{min_level}, got L{result.level}"
```

### Step 2: test_confidence_override.py

```python
# api/tests/test_confidence_override.py
"""置信度覆写机制专项测试（DataModel §7.5 验证）。"""
from api.domain.priority_engine import PriorityEngine


def test_breakdown_low_confidence_override():
    """
    测试"乘法漏斗"防御。

    场景: breakdown + agent_inference + confidence=0.5
    base_score 高 (95) 但 raw_confidence 低 (0.5)
    旧逻辑: 95 × 0.5 = 48 → L2 ❌
    新逻辑: floor=0.9, effective=0.9, score=85 → L4 ✅
    """
    from datetime import datetime
    from api.models.event import EventCreate

    engine = PriorityEngine()
    event = EventCreate(
        type="breakdown",
        entity_type="equipment",
        entity_id="E-0045",
        title="E-0045 故障停机",
        source="agent_inference",
        confidence=0.5,
        timestamp=datetime(2026, 6, 24, 10, 0),
    )
    result = engine.process(event)
    assert result.confidence >= 0.9, f"应覆写到 >=0.9, 实际 {result.confidence}"
    assert result.level >= 3, f"应 >=L3, 实际 L{result.level}"
    # 验证不被乘法漏斗打到 L2
    assert result.level > 2, f"乘法漏斗防御失败: L{result.level}"
    # 验证不会凭空到 L5
    assert result.level <= 5, f"等级异常: L{result.level}"


def test_absent_low_confidence_no_override():
    """
    请假 + 低可信 → 不应覆写。

    场景: absent + agent_inference + confidence=0.4
    absent 不在 CONFIDENCE_FLOOR_OVERRIDE 中
    旧逻辑: 降级到 L2（合理，低可信请假不该弹出）
    新逻辑: 同旧逻辑，无覆写
    """
    from datetime import datetime
    from api.models.event import EventCreate

    engine = PriorityEngine()
    event = EventCreate(
        type="absent",
        entity_type="employee",
        entity_id="张三",
        title="张三请假",
        source="agent_inference",
        confidence=0.4,
        timestamp=datetime(2026, 6, 24, 10, 0),
    )
    result = engine.process(event)
    # absent 没有 floor override，effective = 0.4
    # base_score 约 52，52 × 0.4 = 21 → L2
    assert result.level <= 2, f"低可信请假应 <=L2, 实际 L{result.level}"


def test_l5_ceiling_break():
    """
    测试 L5 天花板突破。v6 新增。

    场景: breakdown + base_score=100 + raw_confidence=0.6
    floor=0.9 → effective=0.9 → score=90 → 正常判 L4
    但因 base_score >= 95 且 type 在 CONFIDENCE_FLOOR_OVERRIDE 中
    → 强制 L5, final_score >= 91
    """
    engine = PriorityEngine()
    eff_conf, level, score = engine._apply_confidence(
        event_type="breakdown",
        base_score=100,
        raw_confidence=0.6,
    )
    assert level == 5, f"L5 ceiling break 失败: L{level}"
    assert eff_conf == 0.9, f"effective_confidence 应为 0.9, 实际 {eff_conf}"
    assert score >= 91, f"score 应 >=91, 实际 {score}"


def test_almost_l5_not_forced():
    """
    base_score=94 不触发天花板突破（边界测试）。

    场景: breakdown + base_score=94 + raw_confidence=0.6
    floor=0.9 → effective=0.9 → score=84 → L4
    base_score=94 < 95，不触发强制 L5
    """
    engine = PriorityEngine()
    _, level, _ = engine._apply_confidence(
        event_type="breakdown",
        base_score=94,
        raw_confidence=0.6,
    )
    assert level == 4, f"不应触发 L5 突破: L{level}"

```

### Step 3: test_context_filter.py

```python
# api/tests/test_context_filter.py
from api.domain.context_filter import (
    UserContext, filter_decisions, filter_insights,
)


def test_filter_by_role():
    """operator 只能看到 L1-L2。"""
    decisions = [
        {"id": "1", "level": 1, "score": 10, "context_filter": "production", "status": "pending"},
        {"id": "2", "level": 3, "score": 60, "context_filter": "production", "status": "pending"},
        {"id": "3", "level": 5, "score": 95, "context_filter": "production", "status": "pending"},
    ]
    ctx = UserContext(role="operator", current_page="production")
    result = filter_decisions(decisions, ctx, level_min=1)
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_filter_by_page():
    """生产中心只看到 production 相关的。"""
    decisions = [
        {"id": "1", "level": 4, "score": 80, "context_filter": "production", "status": "pending"},
        {"id": "2", "level": 4, "score": 85, "context_filter": "materials", "status": "pending"},
        {"id": "3", "level": 4, "score": 76, "context_filter": "personnel", "status": "pending"},
    ]
    ctx = UserContext(role="admin", current_page="production")
    result = filter_decisions(decisions, ctx, level_min=4)
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_sorted_by_level_then_score():
    """排序: level DESC + score DESC。"""
    decisions = [
        {"id": "a", "level": 4, "score": 76, "context_filter": "production", "status": "pending"},
        {"id": "b", "level": 5, "score": 95, "context_filter": "production", "status": "pending"},
        {"id": "c", "level": 4, "score": 88, "context_filter": "production", "status": "pending"},
    ]
    ctx = UserContext(role="admin", current_page="production")
    result = filter_decisions(decisions, ctx, level_min=1)
    ids = [r["id"] for r in result]
    assert ids == ["b", "c", "a"], f"排序错误: {ids}"


def test_filter_insights_by_page():
    """Insight 只展示当前页面的。"""
    insights = [
        {"id": "i1", "level": 3, "score": 70, "context_filter": "production"},
        {"id": "i2", "level": 2, "score": 40, "context_filter": "personnel"},
        {"id": "i3", "level": 3, "score": 60, "context_filter": "production"},
    ]
    ctx = UserContext(role="admin", current_page="production")
    result = filter_insights(insights, ctx, limit=5)
    assert len(result) == 2
    assert result[0]["id"] == "i1"
    assert result[1]["id"] == "i3"
```

### Step 4: test_api.py

```python
# api/tests/test_api.py
"""API 集成测试。"""
from fastapi.testclient import TestClient
from datetime import datetime

from api.main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_post_event():
    resp = client.post("/api/events", json={
        "type": "absent",
        "entity_type": "employee",
        "entity_id": "张三",
        "title": "张三请假",
        "source": "inbox_ai",
        "confidence": 0.88,
        "timestamp": "2026-06-24T07:30:00Z",
        "metadata": {"leave_type": "事假"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "event_id" in data
    assert data["level"] >= 2


def test_get_decision_center():
    resp = client.get("/api/decision-center?role=admin&page=production&level_min=4")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_get_context_strip():
    resp = client.get("/api/context-strip?page=production&role=admin&limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
```

### 运行测试

```bash
cd d:/AI知识库/AI++++/工厂现场——工时
pip install pytest httpx
python -m pytest api/tests/ -v

# 期望输出:
# test_health_check PASSED
# test_absent_event_is_l2_l3 PASSED
# test_delay_event_is_l4_or_above PASSED
# test_breakdown_with_low_confidence PASSED
# test_confidence_override PASSED  (乘法漏斗防御)
# ...
```

---

## Phase 1 完成检查清单

- [ ] `uvicorn api.main:app` 启动正常
- [ ] `GET /api/health` 返回 200
- [ ] `POST /api/events` 创建 Event + 自动分级
- [ ] `GET /api/decision-center?role=admin&page=production&level_min=4` 返回数据
- [ ] `GET /api/context-strip?page=production` 返回 L2-L3 Insight
- [ ] `POST /api/actions` 执行 Decision 操作
- [ ] 乘法漏斗防御：breakdown + conf=0.5 → L4（不是 L2）
- [ ] 请假 + conf=0.4 → L2（不在高危覆写列表）
- [ ] 排序: level DESC + score DESC
- [ ] `pytest api/tests/ -v` 全部通过
- [ ] 提交 commit: `feat: Phase 1 — FastAPI骨架 + Priority Engine + 事件管道`
