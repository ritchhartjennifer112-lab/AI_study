# api/config.py
"""应用配置，从环境变量读取，有合理默认值。"""
from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件（无需 python-dotenv 依赖）
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _value = _line.partition("=")
                _key, _value = _key.strip(), _value.strip()
                if _key and _key not in os.environ:
                    os.environ[_key] = _value


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
