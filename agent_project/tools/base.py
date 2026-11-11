from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel


class BaseTool(ABC):
    """所有工具的基类：声明三样东西即可接入。

    name / description：给模型看的元数据；
    args_model：参数模型，schema 自动生成，运行时也用它校验。
    """

    name: ClassVar[str]
    description: ClassVar[str]
    args_model: ClassVar[type[BaseModel]]
    schema: ClassVar[dict[str, Any]]

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.schema = cls.args_model.model_json_schema()

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


def safe_path(path: str, workspace: Path) -> Path:
    """把路径限制在工作区内；比 startswith 更稳，避免 work_evil 绕过。"""
    root = workspace.resolve()
    candidate = Path(path)
    abs_path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not abs_path.is_relative_to(root):
        raise ValueError(f"Access to path '{path}' is denied.")
    return abs_path


def truncate(text: str, limit: int = 32000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, {len(text)} chars total]"
