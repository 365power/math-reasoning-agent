from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseTool
from .file_tools import ListFilesTool, ReadFileTool, WriteFileTool
from .python_tool import PythonTool


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    python_timeout: int = 30


# 工具注册表：新增工具只改这里，工具清单和实例化都会自动跟上。
_TOOL_FACTORIES: dict[type[BaseTool], Callable[[ToolContext], BaseTool]] = {
    PythonTool: lambda ctx: PythonTool(ctx.workspace, default_timeout=ctx.python_timeout),
    ReadFileTool: lambda ctx: ReadFileTool(ctx.workspace),
    WriteFileTool: lambda ctx: WriteFileTool(ctx.workspace),
    ListFilesTool: lambda ctx: ListFilesTool(ctx.workspace),
}

TOOL_CLASSES: tuple[type[BaseTool], ...] = tuple(_TOOL_FACTORIES)


def tools() -> list[dict[str, Any]]:
    """OpenAI Function Calling 格式的工具定义；只读类属性，不实例化。"""
    return [
        {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.schema,
            },
        }
        for cls in TOOL_CLASSES
    ]


def build_tools(ctx: ToolContext) -> dict[str, BaseTool]:
    return {cls.name: factory(ctx) for cls, factory in _TOOL_FACTORIES.items()}
