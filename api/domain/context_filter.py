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

        # 语境过滤：只展示与当前页面相关的消息
        d_context = d.get("context_filter", "")
        if d_context and d_context not in allowed_contexts:
            continue
        if d_context and context.current_page and d_context != context.current_page:
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
