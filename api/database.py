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
    from core.ddl import apply_migration_v2
    apply_migration_v2()
    Base.metadata.create_all(bind=engine)
