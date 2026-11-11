from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    reasoning_content: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    if value is None:
        extra = getattr(obj, "model_extra", None) or {}
        value = extra.get(name, default)
    return value


def _usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
        }
    details = _get(usage, "completion_tokens_details")
    return {
        "prompt_tokens": int(_get(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(_get(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(_get(usage, "total_tokens", 0) or 0),
        "reasoning_tokens": int(_get(details, "reasoning_tokens", 0) or 0)
        if details is not None
        else 0,
    }


class LLMClient:
    """OpenAI 兼容客户端，返回项目自己的 LLMResponse，隔离厂商回包差异。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 1.0,
        top_p: float = 0.95,
        max_tokens: int = 16384,
    ):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=600.0,
            max_retries=0,
        )

    def _create_with_retry(self, kwargs: dict[str, Any], attempts: int = 3):
        for attempt in range(attempts):
            try:
                return self.client.chat.completions.create(**kwargs)
            except (APITimeoutError, APIConnectionError):
                if attempt == attempts - 1:
                    raise
                time.sleep(2.0 * (attempt + 1))
            except APIStatusError as exc:
                message = str(exc)
                transient = exc.status_code in (429, 500, 502, 503, 504) or (
                    exc.status_code == 400 and "Invalid model id" in message
                )
                if not transient or attempt == attempts - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature if temperature is None else temperature,
            "top_p": self.top_p if top_p is None else top_p,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        response = self._create_with_retry(kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        for call in (_get(msg, "tool_calls", None) or []):
            fn = _get(call, "function")
            tool_calls.append(
                ToolCall(
                    id=str(_get(call, "id", "")),
                    name=str(_get(fn, "name", "")),
                    arguments=str(_get(fn, "arguments", "") or "{}"),
                )
            )

        content = _get(msg, "content")
        return LLMResponse(
            content=None if content is None else str(content),
            tool_calls=tool_calls,
            finish_reason=str(_get(choice, "finish_reason", "")) or None,
            reasoning_content=_get(msg, "reasoning_content"),
            usage=_usage_dict(_get(response, "usage")),
        )


# ---------------------------------------------------------------------------
# Mock 客户端：不需要 API key，用于验证整条流水线
# ---------------------------------------------------------------------------
_MOCK_PYTHON = """\
import math
partial = 0.0
for n in range(1, 300000):
    partial += math.atan(1.0 / (2.0 * n * n))
print(f"partial_sum={partial:.15f}")
print(f"pi_over_4={math.pi / 4:.15f}")
"""

_MOCK_FINAL = """\
Use the arctangent difference identity
$\\arctan a-\\arctan b=\\arctan\\frac{a-b}{1+ab}$.

Take $a=2n+1,\\ b=2n-1$. Then
$$\\frac{a-b}{1+ab}=\\frac{2}{1+(2n+1)(2n-1)}
=\\frac{2}{4n^2}=\\frac{1}{2n^2},$$
so
$$\\arctan\\frac{1}{2n^2}=\\arctan(2n+1)-\\arctan(2n-1).$$

The partial sum telescopes:
$$S_N=\\sum_{n=1}^{N}\\left[\\arctan(2n+1)-\\arctan(2n-1)\\right]
=\\arctan(2N+1)-\\arctan 1.$$

As $N\\to\\infty$, $\\arctan(2N+1)\\to\\frac{\\pi}{2}$, hence
$$\\sum_{n=1}^{\\infty}\\arctan\\frac{1}{2n^2}
=\\frac{\\pi}{2}-\\frac{\\pi}{4}=\\frac{\\pi}{4}.$$

\\boxed{\\frac{\\pi}{4}}
"""


class MockLLMClient:
    """第一次调用返回一个 python 工具调用，看到工具结果后返回最终答案。"""

    model = "mock-deepseek-v4.1-flash-1017"
    temperature = 1.0
    top_p = 0.95
    max_tokens = 16384

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if not has_tool_result:
            return LLMResponse(
                content="I will first verify the partial sums numerically, then give the rigorous derivation.",
                tool_calls=[
                    ToolCall(
                        id="call_mock_001",
                        name="python",
                        arguments=json.dumps(
                            {"code": _MOCK_PYTHON, "timeout": 30},
                            ensure_ascii=False,
                        ),
                    )
                ],
                finish_reason="tool_calls",
                reasoning_content="Run a numerical check first to avoid a wrong derivation direction.",
                usage={
                    "prompt_tokens": 600,
                    "completion_tokens": 120,
                    "total_tokens": 720,
                    "reasoning_tokens": 80,
                },
            )
        return LLMResponse(
            content=_MOCK_FINAL,
            tool_calls=[],
            finish_reason="stop",
            reasoning_content="The numerical result is about 0.785398, matching pi/4; use the arctangent difference identity to telescope the series.",
            usage={
                "prompt_tokens": 900,
                "completion_tokens": 500,
                "total_tokens": 1400,
                "reasoning_tokens": 260,
            },
        )
