# api/main.py
"""Factory OS FastAPI 应用入口。"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.database import init_db
from api.routers import events, decisions, context_strip, actions, auth
from api.routers.business import router as business_router
from api.routers.decision_history import router as history_router
from api.routers.admin import router as admin_router
from api.routers.copilot import router as copilot_router

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

# Route registration (module level, before startup — TestClient compatible)
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(decisions.router)
app.include_router(context_strip.router)
app.include_router(actions.router)
app.include_router(business_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(copilot_router)


@app.on_event("startup")
def on_startup():
    init_db()
    from api.scheduler import scheduler
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    from api.scheduler import scheduler
    scheduler.stop()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
