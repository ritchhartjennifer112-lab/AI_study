"""工具注册表：把现有 core/ 函数注册为可被执行器调用的工具。"""
import inspect
from dataclasses import dataclass, field


@dataclass
class ToolInfo:
    名称: str
    描述: str
    函数: callable
    参数签名: dict = field(default_factory=dict)


class ToolRegistry:
    """管理所有可用工具的注册与调用。"""

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(self, 名称: str, 描述: str):
        """装饰器：注册一个函数为工具。"""
        def decorator(func):
            sig = inspect.signature(func)
            params = {
                name: str(p.annotation) if p.annotation != inspect.Parameter.empty else "any"
                for name, p in sig.parameters.items()
                if name != "ctx"
            }
            self._tools[名称] = ToolInfo(
                名称=名称,
                描述=描述,
                函数=func,
                参数签名=params,
            )
            return func
        return decorator

    def call(self, 名称: str, ctx: dict = None, **kwargs):
        """调用已注册工具。ctx 为执行上下文（可选）。"""
        if 名称 not in self._tools:
            raise KeyError(f"工具 '{名称}' 未注册。可用工具: {list(self._tools.keys())}")
        tool = self._tools[名称]
        sig = inspect.signature(tool.函数)
        if "ctx" in sig.parameters:
            return tool.函数(ctx=ctx, **kwargs)
        return tool.函数(**kwargs)

    def list_tools(self) -> list[dict]:
        """列出所有已注册工具的名称和描述。"""
        return [{"名称": t.名称, "描述": t.描述, "参数": t.参数签名}
                for t in self._tools.values()]

    def get_tool(self, 名称: str) -> ToolInfo | None:
        return self._tools.get(名称)
