# api/routers/actions.py
"""POST /api/actions — 执行操作。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import get_current_user
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
def execute_action(req: ActionRequest, db: Session = Depends(get_db), _user=Depends(get_current_user)):
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
