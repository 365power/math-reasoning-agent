from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = PROJECT_ROOT / "cases"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
WORKSPACE_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    judge_api_key: str
    judge_base_url: str
    judge_model: str
    temperature: float
    top_p: float
    max_tokens: int
    rollouts: int
    max_tool_rounds: int
    tool_timeout: int
    workspace: Path

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key) and self.api_key != "sk-REPLACE_ME"

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = _env("DEEPSEEK_API_KEY")
        base_url = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = _env("DEEPSEEK_MODEL", "deepseek-flash")

        judge_api_key = _env("JUDGE_API_KEY") or api_key
        judge_base_url = _env("JUDGE_BASE_URL") or base_url
        judge_model = _env("JUDGE_MODEL") or model

        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            judge_api_key=judge_api_key,
            judge_base_url=judge_base_url,
            judge_model=judge_model,
            temperature=_env_float("TEMPERATURE", 1.0),
            top_p=_env_float("TOP_P", 0.95),
            max_tokens=_env_int("MAX_TOKENS", 16384),
            rollouts=_env_int("ROLLOUTS", 8),
            max_tool_rounds=_env_int("MAX_TOOL_ROUNDS", 12),
            tool_timeout=_env_int("TOOL_TIMEOUT", 30),
            workspace=WORKSPACE_DIR,
        )
