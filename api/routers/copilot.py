# api/routers/copilot.py
"""Copilot Chat — SSE 流式对话端点。"""
from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import get_db
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

SYSTEM_PROMPT = """你是工厂工时管理系统的智能助理。你可以：

1. 回答工厂数据查询问题（工单状态、人员工时、效率分析、缺料情况等）
2. 帮助分析生产数据（效率趋势、异常检测、派工建议）
3. 解释系统功能和数据含义

回答要求：
- 用简洁的中文回复，直接给出结论和数据
- 如果数据不在上下文中，诚实说不知道，不要编造
- 对于数据分析类问题，给出洞察而不仅仅是数据罗列
- 如果用户问系统操作问题，给出操作步骤
- 使用 Markdown 格式排版，重要数字用 **粗体**"""


@router.post("/chat")
async def copilot_chat(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """SSE 流式对话端点。接收 {messages: [{role, content}]}，返回 SSE 事件流。

    SSE 事件类型:
    - text: 文本 token chunk
    - done: 对话完成
    - error: 异常信息
    """
    body = await request.json()
    messages = body.get("messages", [])

    if not messages:
        return StreamingResponse(
            _sse_event("error", {"message": "messages is required"}),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _stream_chat(messages, SYSTEM_PROMPT),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_chat(messages: list[dict], system: str):
    """生成 SSE 事件流。"""
    try:
        from core.agent.llm_client import create_streaming_llm_call

        stream_fn = create_streaming_llm_call()
        full_text = ""

        for chunk in stream_fn(messages, system=system):
            full_text += chunk
            yield _sse_event("text", {"content": chunk})
            await asyncio.sleep(0)

        yield _sse_event("done", {"full_text": full_text})

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})


def _sse_event(event_type: str, data: dict) -> str:
    """格式化 SSE 事件。"""
    payload = json.dumps({**data, "type": event_type}, ensure_ascii=False)
    return f"data: {payload}\n\n"
