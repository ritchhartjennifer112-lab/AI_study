# api/dependencies.py
"""FastAPI 依赖注入 — JWT 认证 + 角色控制。"""
from __future__ import annotations
from datetime import datetime, timedelta
import uuid
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.models.user import UserModel

security_scheme = HTTPBearer()


def create_access_token(user_id: str, username: str, role: str) -> dict:
    """生成 JWT。返回 token 字符串和过期信息。"""
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": expire,
        "jti": uuid.uuid4().hex[:12],
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "access_token": token,
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "role": role,
    }


def decode_token(token: str) -> dict:
    """解码 JWT，无效或过期时抛出 HTTPException。"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """从 Bearer token 提取当前用户信息（不查 DB）。"""
    payload = decode_token(credentials.credentials)
    return {
        "user_id": payload["sub"],
        "username": payload["username"],
        "role": payload.get("role", "operator"),
    }


def get_current_active_user(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取当前用户，并验证用户仍为 active 状态（查 DB）。"""
    user = db.query(UserModel).filter(UserModel.id == current_user["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive or deleted")
    return current_user


def require_role(*roles: str):
    """依赖工厂：限制访问角色。用法: Depends(require_role("admin", "supervisor"))"""

    def _check(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user['role']}' not allowed. Required: {roles}",
            )
        return current_user

    return _check
