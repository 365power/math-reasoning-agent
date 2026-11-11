from __future__ import annotations

from pydantic import BaseModel, Field

from .base import BaseTool, safe_path, truncate


class ReadFileArgs(BaseModel):
    path: str = Field(description="Relative path inside the workspace, e.g. notes/lemma.txt")
    start: int = Field(default=1, ge=1, description="First line number (1-based)")
    end: int | None = Field(default=None, ge=1, description="Last line number (inclusive); omit to read to the end")


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a text file inside the workspace, optionally by line range."
    args_model = ReadFileArgs

    def run(self, path: str, start: int = 1, end: int | None = None) -> str:
        try:
            target = safe_path(path, self.workspace)
            if not target.exists():
                return f"Error: file not found: {path}"
            if not target.is_file():
                return f"Error: not a file: {path}"
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except ValueError as exc:
            return f"Error: {exc}"
        except OSError as exc:
            return f"Error: {type(exc).__name__}: {exc}"

        selected = lines[start - 1 : end]
        body = "\n".join(f"{start + i:>4}| {line}" for i, line in enumerate(selected))
        return truncate(body or "(empty file)")


class WriteFileArgs(BaseModel):
    path: str = Field(description="Relative path inside the workspace")
    content: str = Field(description="Full text to write")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write text to a file inside the workspace, overwriting existing content; parent directories are created automatically."
    args_model = WriteFileArgs

    def run(self, path: str, content: str) -> str:
        try:
            target = safe_path(path, self.workspace)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except ValueError as exc:
            return f"Error: {exc}"
        except OSError as exc:
            return f"Error: {type(exc).__name__}: {exc}"
        return f"Wrote {len(content)} characters to {path}"


class ListFilesArgs(BaseModel):
    pattern: str = Field(default="*", description="Glob pattern, e.g. *.py or **/*.txt")


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "List files inside the workspace matching a glob pattern, returning relative paths."
    args_model = ListFilesArgs

    def run(self, pattern: str = "*") -> str:
        try:
            matches = sorted(
                str(p.relative_to(self.workspace)).replace("\\", "/")
                for p in self.workspace.glob(pattern)
                if p.is_file()
            )
        except (ValueError, OSError) as exc:
            return f"Error: {type(exc).__name__}: {exc}"
        return truncate("\n".join(matches) if matches else "(no matches)")
