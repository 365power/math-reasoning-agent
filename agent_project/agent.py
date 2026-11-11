from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import Settings
from .llm import LLMClient, LLMResponse
from .tools import BaseTool, ToolContext, build_tools, tools

MAX_TOOL_RESULT_CHARS = 32000


@dataclass
class RolloutResult:
    messages: list[dict]
    final_content: str
    stop_reason: str
    rounds: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    tool_statistics: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    error: str | None = None


class Agent:
    """s01 的循环 + s02 的分发表，把 LLM 换成 OpenAI 兼容 API。"""

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient | Any,
        workspace: Path | None = None,
    ):
        self.settings = settings
        self.llm = llm
        self.workspace = (workspace or settings.workspace).resolve()
        self._tool_impls: dict[str, BaseTool] | None = None
        self._tool_specs = tools()

    def _tool_instances(self) -> dict[str, BaseTool]:
        """第一次真正执行工具时才实例化（工具可能依赖密钥或工作区状态）。"""
        if self._tool_impls is None:
            self._tool_impls = build_tools(
                ToolContext(
                    workspace=self.workspace,
                    python_timeout=self.settings.tool_timeout,
                )
            )
        return self._tool_impls

    def agent_loop(
        self,
        messages: list[dict],
        max_rounds: int | None = None,
    ) -> RolloutResult:
        limit = max_rounds or self.settings.max_tool_rounds
        trajectory: list[dict] = []
        usage_total = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
        }
        tool_call_counts: dict[str, int] = {}
        successful_tool_calls = 0
        failed_tool_calls = 0
        assistant_rounds = 0
        start = time.perf_counter()

        final_content = ""
        stop_reason = "max_tool_rounds"
        error: str | None = None

        try:
            while True:
                if assistant_rounds >= limit:
                    stop_reason = "max_tool_rounds"
                    break

                response: LLMResponse = self.llm.chat(
                    messages,
                    tools=self._tool_specs,
                    tool_choice="auto",
                )
                assistant_rounds += 1
                _add_usage(usage_total, response.usage)

                if not response.tool_calls:
                    messages.append(
                        {"role": "assistant", "content": response.content}
                    )
                    trajectory.append(
                        {
                            "role": "assistant",
                            "content": response.content,
                            "reasoning_content": response.reasoning_content,
                        }
                    )
                    final_content = response.content or ""
                    stop_reason = response.finish_reason or "model_finished"
                    break

                api_tool_calls = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    }
                    for call in response.tool_calls
                ]
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": api_tool_calls,
                    }
                )
                trajectory.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "reasoning_content": response.reasoning_content,
                        "tool_calls": api_tool_calls,
                    }
                )

                impls = self._tool_instances()
                for call in response.tool_calls:
                    tool_call_counts[call.name] = tool_call_counts.get(call.name, 0) + 1
                    result = self._execute(impls, call.name, call.arguments)
                    failed = isinstance(result, dict) and "error" in result
                    if failed:
                        failed_tool_calls += 1
                    else:
                        successful_tool_calls += 1

                    content = json.dumps(
                        result, ensure_ascii=False, default=str
                    )[:MAX_TOOL_RESULT_CHARS]
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": content,
                        }
                    )
                    trajectory.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": content,
                        }
                    )
        except Exception as exc:  # noqa: BLE001 - 单次 rollout 失败不能拖垮整批
            stop_reason = "error"
            error = f"{type(exc).__name__}: {exc}"
        finally:
            duration = time.perf_counter() - start

        total_tool_calls = sum(tool_call_counts.values())
        if error:
            termination = {"type": "error", "reason": "error", "error": error}
        elif stop_reason == "max_tool_rounds":
            termination = {"type": "max_rounds", "reason": "max_tool_rounds"}
        elif stop_reason in {"length", "max_tokens"}:
            termination = {"type": "length", "reason": "max_tokens"}
        else:
            termination = {"type": "answer", "reason": "model_finished"}
        stats = {
            "tool_call_counts": tool_call_counts,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "statistics": {
                "total_rounds": assistant_rounds,
                "assistant_rounds": assistant_rounds,
                "tool_rounds": total_tool_calls,
            },
            "termination": termination,
        }
        return RolloutResult(
            messages=trajectory,
            final_content=final_content,
            stop_reason=stop_reason,
            rounds=assistant_rounds,
            usage=usage_total,
            tool_statistics=stats,
            duration_seconds=duration,
            error=error,
        )

    @staticmethod
    def _execute(
        impls: dict[str, BaseTool],
        name: str,
        raw_args: str,
    ) -> Any:
        tool = impls.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}

        try:
            args = tool.args_model.model_validate_json(raw_args or "{}")
        except ValidationError as exc:
            return {"error": f"invalid arguments for {name}: {exc}"}

        try:
            return tool.run(**args.model_dump())
        except Exception as exc:  # noqa: BLE001 - 工具异常转文本回给模型
            return {"error": f"{type(exc).__name__}: {exc}"}


def _add_usage(total: dict[str, int], usage: dict[str, int]) -> None:
    for key in total:
        total[key] += int(usage.get(key, 0) or 0)
