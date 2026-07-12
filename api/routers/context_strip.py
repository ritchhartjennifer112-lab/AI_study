# api/routers/context_strip.py
"""GET /api/context-strip — AI Context Strip 内容。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import get_current_user
from api.services.notification_service import NotificationService

router = APIRouter(prefix="/api", tags=["context-strip"])


@router.get("/context-strip")
def get_context_strip(
    page: str = Query(...),
    role: str = Query("admin"),
    limit: int = Query(3),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """获取 AI Context Strip 内容。

    - page: 当前页面
    - role: 角色
    - limit: 返回条数上限
    """
    service = NotificationService(db)
    items = service.get_context_strip(page=page, role=role, limit=limit)
    return {"items": items}
