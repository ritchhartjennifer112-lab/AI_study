# api/routers/decisions.py
"""GET /api/decision-center — 决策查询。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import get_current_user
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
    _user=Depends(get_current_user),
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
