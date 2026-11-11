from __future__ import annotations

import json
import re
from pathlib import Path

from ..case import Case
from ..config import PROJECT_ROOT
from .models import TaskSpec


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "task"


def _resolve_case(raw: str, base: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    candidate = (PROJECT_ROOT / path).resolve()
    if candidate.is_file():
        return candidate
    return (base / path).resolve()


def load_tasks(path: Path) -> list[TaskSpec]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        items = json.loads(stripped)
    else:
        items = [json.loads(line) for line in text.splitlines() if line.strip()]

    tasks: list[TaskSpec] = []
    for index, item in enumerate(items, start=1):
        raw_case = item.get("case") or item.get("case_path")
        if not raw_case:
            raise ValueError(f"task #{index}: missing 'case'")
        case_path = _resolve_case(str(raw_case), path.parent)
        rollout_id = int(item.get("rollout_id", index))
        task_id = str(item.get("id") or f"{case_path.stem}#r{rollout_id:02d}")
        tasks.append(
            TaskSpec(
                id=task_id,
                case_path=str(case_path),
                rollout_id=rollout_id,
                timeout_s=item.get("timeout_s"),
                metadata=item.get("metadata", {}),
            )
        )
    validate_tasks(tasks)
    return tasks


def expand_case(case_path: Path, rollouts: int) -> list[TaskSpec]:
    case = Case.load(case_path)
    return [
        TaskSpec(
            id=f"{case.id}#r{i:02d}",
            case_path=str(case_path.resolve()),
            rollout_id=i,
        )
        for i in range(1, rollouts + 1)
    ]


def validate_tasks(tasks: list[TaskSpec]) -> None:
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate task ids: {dupes}")
    for task in tasks:
        if not Path(task.case_path).is_file():
            raise ValueError(f"{task.id}: case file not found: {task.case_path}")
