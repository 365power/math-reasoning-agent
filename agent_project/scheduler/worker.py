from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import replace
from pathlib import Path

from ..case import Case
from ..clients import build_clients
from ..config import Settings
from ..runner import SYSTEM_PROMPT, run_case
from .models import WorkerJob


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _error_record(job: WorkerJob, error: str) -> dict:
    return {
        "task_id": job.task.id,
        "run_id": job.run_id,
        "case_id": job.case_id,
        "rollout_id": job.task.rollout_id,
        "status": "error",
        "error": error,
        "termination": {"reason": "error", "error": error},
    }


def run_job(job: WorkerJob) -> None:
    try:
        settings = Settings.from_env()
        if job.model:
            settings = replace(settings, model=job.model)
        settings = replace(settings, workspace=Path(job.workspace))
        if not job.mock and not settings.has_api_key:
            raise RuntimeError("未检测到 DEEPSEEK_API_KEY，无法调用真实模型")

        case = Case.load(job.case_path)
        client, judge_client, use_llm_judge = build_clients(
            settings, job.mock, job.use_llm_judge
        )

        result_doc, metrics = run_case(
            settings=settings,
            case=case,
            client=client,
            judge_client=judge_client,
            rollouts=1,
            use_llm_judge=use_llm_judge,
            progress=None,
        )
        record = dict(result_doc["rollout_35B_results"][0])
        termination = record.get("termination", {})
        status = "error" if termination.get("reason") == "error" else "success"
        record.update(
            {
                "task_id": job.task.id,
                "run_id": job.run_id,
                "case_id": case.id,
                "rollout_id": job.task.rollout_id,
                "status": status,
                "mock": job.mock,
                "model": metrics["parameters"]["model"],
                "workspace": job.workspace,
                "judge_usage": metrics["metrics"]["judge_usage"],
            }
        )

        _write_json(
            job.trajectory_path,
            {"system": SYSTEM_PROMPT, "messages": record["messages"]},
        )
        _write_json(job.record_path, record)
    except Exception:  # noqa: BLE001 - worker 崩溃也要留下可读记录
        _write_json(job.record_path, _error_record(job, traceback.format_exc()[-4000:]))


def main() -> int:
    parser = argparse.ArgumentParser(description="math scheduler worker")
    parser.add_argument("--job", required=True)
    args = parser.parse_args()

    job = WorkerJob.model_validate_json(
        Path(args.job).read_text(encoding="utf-8")
    )
    run_job(job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
