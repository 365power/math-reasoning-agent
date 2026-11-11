from __future__ import annotations

import os
import subprocess
import sys

from pydantic import BaseModel, Field

from .base import BaseTool, truncate


class PythonArgs(BaseModel):
    code: str = Field(description="Python code to execute. The standard library is available; sympy is available if installed.")
    timeout: int = Field(default=30, ge=1, le=120, description="Timeout in seconds, 1 to 120.")


class PythonTool(BaseTool):
    name = "python"
    description = (
        "Execute Python code in an isolated subprocess and return stdout/stderr."
        "Useful for numerical checks, symbolic computation, and verifying partial sums."
        "Note: this is not a security sandbox; only use it in a controlled environment."
    )
    args_model = PythonArgs

    def __init__(self, workspace, default_timeout: int = 30):
        super().__init__(workspace)
        self.default_timeout = default_timeout

    def run(self, code: str, timeout: int | None = None) -> str:
        limit = int(timeout or self.default_timeout)
        limit = max(1, min(limit, 120))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            # -I 会忽略 PYTHONIOENCODING/PYTHONUTF8，必须用 -X utf8 固定子进程编码；
            # 否则中文/Unicode 输出按 GBK 编码，父进程按 UTF-8 解码后变成 U+FFFD。
            proc = subprocess.run(
                [sys.executable, "-I", "-X", "utf8", "-"],
                input=code,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=limit,
                cwd=str(self.workspace),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return f"Error: execution timed out after {limit}s"
        except Exception as exc:  # noqa: BLE001 - 工具边界必须兜底
            return f"Error: {type(exc).__name__}: {exc}"

        parts = [f"exit_code: {proc.returncode}"]
        if proc.stdout:
            parts.append("stdout:\n" + proc.stdout.rstrip())
        if proc.stderr:
            parts.append("stderr:\n" + proc.stderr.rstrip())
        if not proc.stdout and not proc.stderr:
            parts.append("(no output)")
        return truncate("\n".join(parts))
