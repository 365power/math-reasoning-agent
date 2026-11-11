from __future__ import annotations

from typing import Any

from .config import Settings
from .llm import LLMClient, MockLLMClient


def build_clients(
    settings: Settings,
    mock: bool,
    use_llm_judge: bool,
) -> tuple[Any, Any, bool]:
    """构造解题模型与评分模型；mock 模式强制走启发式评分。"""
    if mock:
        client = MockLLMClient()
        return client, client, False

    client = LLMClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        temperature=settings.temperature,
        top_p=settings.top_p,
        max_tokens=settings.max_tokens,
    )
    if (
        settings.judge_api_key == settings.api_key
        and settings.judge_base_url == settings.base_url
        and settings.judge_model == settings.model
    ):
        judge_client = client
    else:
        judge_client = LLMClient(
            api_key=settings.judge_api_key,
            base_url=settings.judge_base_url,
            model=settings.judge_model,
            temperature=0.0,
            top_p=1.0,
            max_tokens=2048,
        )
    return client, judge_client, use_llm_judge
