from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..case import Case
from ..config import PROJECT_ROOT, Settings
from ..integrate import (
    DEFAULT_ROLLOUTS,
    build_delivery_record,
    dump_record_json,
    write_delivery_by_domain,
)
from ..report import render_markdown
from ..runner import SYSTEM_PROMPT, summarize_records
from ..validation import DOMAIN_SLUGS, validate_delivery_record
from .models import TaskOutcome, TaskSpec, WorkerJob
from .records import append_delivery, render_batch_report
from .tasks import slugify, validate_tasks


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunConfig:
    output_dir: Path = PROJECT_ROOT / "outputs" / "scheduler"
    batch: str = "batch01"
    run_id: str = ""
    concurrency: int = 4
    timeout_s: float = 1800.0
    mock: bool = False
    use_llm_judge: bool = True
    model: str | None = None
    limit: int = 0
    readable_delivery: bool = False


class Scheduler:
    """协调器：只负责起 worker 子进程、等待、读记录、汇总；不调模型、不执行工具。"""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.settings = Settings.from_env()
        self.run_id = config.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = config.output_dir.resolve()
        self.run_dir = self.output_dir / "runs" / self.run_id
        self.progress_path = self.output_dir / f"{config.batch}_progress.jsonl"
        self.delivery_dir = self.output_dir / "delivery"
        self.model = config.model or self.settings.model
        self._case_cache: dict[str, Case] = {}
        self._delivery_lock = threading.Lock()
        self._case_records: dict[str, dict[str, Any]] = {}

    def _case(self, path: str) -> Case:
        if path not in self._case_cache:
            self._case_cache[path] = Case.load(path)
        return self._case_cache[path]

    # ---------- 单任务 ----------

    def _run_one(self, task: TaskSpec, case: Case) -> TaskOutcome:
        t0 = time.perf_counter()
        slug = slugify(task.id)
        task_dir = self.run_dir / "tasks" / slug
        workspace = self.run_dir / "workspaces" / slug
        task_dir.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)

        job_path = task_dir / "job.json"
        record_path = task_dir / "record.json"
        trajectory_path = task_dir / "trajectory.json"
        log_path = task_dir / "worker.log"
        job = WorkerJob(
            run_id=self.run_id,
            task=task,
            case_id=case.id,
            case_path=task.case_path,
            workspace=str(workspace),
            record_path=str(record_path),
            trajectory_path=str(trajectory_path),
            mock=self.config.mock,
            use_llm_judge=self.config.use_llm_judge,
            model=self.config.model,
        )
        job_path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        if self.config.model:
            env["DEEPSEEK_MODEL"] = self.config.model
        cmd = [
            sys.executable,
            "-m",
            "agent_project.scheduler.worker",
            "--job",
            str(job_path),
        ]
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        timeout = task.timeout_s or self.config.timeout_s
        timed_out = False
        log = ""
        exit_code: int | None = None
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                **kwargs,
            )
            exit_code = proc.returncode
            log = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            log = str(exc.stdout or "") + str(exc.stderr or "")
            log += f"\n[coordinator] timeout after {timeout}s; worker killed\n"
        log_path.write_text(log, encoding="utf-8")

        wall = round(time.perf_counter() - t0, 3)
        record: dict[str, Any] = {}
        if record_path.is_file():
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                record = {}

        if timed_out:
            status = "timeout"
            error = f"timeout after {timeout}s"
        elif not record:
            status = "error"
            tail = log.strip().splitlines()[-8:]
            error = "worker produced no record" + ("\n" + "\n".join(tail) if tail else "")
        else:
            status = str(record.get("status", "success"))
            error = record.get("error")
            if status not in {"success", "error"}:
                status = "error"
                error = error or f"unexpected status: {record.get('status')}"

        evaluation = record.get("evaluation", {}) or {}
        usage = record.get("usage", {}) or {}
        stats = record.get("tool_statistics", {}) or {}
        termination = record.get("termination", {}) or {}

        outcome = TaskOutcome(
            id=task.id,
            case_id=case.id,
            rollout_id=task.rollout_id,
            status=status,  # type: ignore[arg-type]
            answer=record.get("extracted_answer"),
            accuracy=evaluation.get("answer_level_accuracy"),
            step_score=evaluation.get("step_level_score"),
            step_max=case.rubric.total_points,
            tokens=int(usage.get("total_tokens", 0) or 0),
            tool_calls=int(stats.get("total_tool_calls", 0) or 0),
            duration_s=float(record.get("duration_seconds") or wall),
            termination=str(termination.get("reason", "")),
            error=error,
            model=str(record.get("model") or self.model),
            mock=self.config.mock,
            run_id=self.run_id,
            record_path=str(record_path) if record else None,
            trajectory_path=str(trajectory_path) if trajectory_path.is_file() else None,
            log_path=str(log_path),
            workspace=str(workspace),
        )
        (task_dir / "outcome.json").write_text(
            outcome.model_dump_json(indent=2), encoding="utf-8"
        )
        with self._delivery_lock:
            append_delivery(self.progress_path, self._delivery_record(outcome))
        return outcome

    @staticmethod
    def _delivery_record(outcome: TaskOutcome) -> dict[str, Any]:
        return {
            "id": outcome.id,
            "case_id": outcome.case_id,
            "rollout_id": outcome.rollout_id,
            "status": outcome.status,
            "answer": outcome.answer,
            "accuracy": outcome.accuracy,
            "step_score": outcome.step_score,
            "step_max": outcome.step_max,
            "tokens": outcome.tokens,
            "tool_calls": outcome.tool_calls,
            "duration_s": outcome.duration_s,
            "termination": outcome.termination,
            "error": outcome.error,
            "model": outcome.model,
            "mock": outcome.mock,
            "run_id": outcome.run_id,
            "record_path": outcome.record_path,
            "trajectory_path": outcome.trajectory_path,
        }

    # ---------- 整批 ----------

    def run(self, tasks: list[TaskSpec]) -> dict[str, Any]:
        validate_tasks(tasks)
        if not self.config.mock and not self.settings.has_api_key:
            raise RuntimeError(
                "未检测到 DEEPSEEK_API_KEY。请先在 .env 中填入密钥，"
                "或先用 --mock 验证调度器。"
            )

        cases = {task.id: self._case(task.case_path) for task in tasks}
        (self.run_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "workspaces").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "cases").mkdir(parents=True, exist_ok=True)

        started = _now()
        t0 = time.perf_counter()
        total = len(tasks)
        done = 0
        outcomes: dict[str, TaskOutcome] = {}

        print(
            f"run {self.run_id}: {total} tasks, concurrency={self.config.concurrency}, "
            f"mock={self.config.mock}, "
            f"judge={'llm' if self.config.use_llm_judge and not self.config.mock else 'heuristic'}, "
            f"model={self.model}"
        )

        workers = max(1, min(self.config.concurrency, total))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._run_one, task, cases[task.id]): task for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    outcome = future.result()
                except Exception as exc:  # noqa: BLE001 - 单任务意外不拖垮整批
                    outcome = TaskOutcome(
                        id=task.id,
                        case_id=cases[task.id].id,
                        rollout_id=task.rollout_id,
                        status="error",
                        error=f"coordinator error: {type(exc).__name__}: {exc}",
                        model=self.model,
                        mock=self.config.mock,
                        run_id=self.run_id,
                    )
                    with self._delivery_lock:
                        append_delivery(self.progress_path, self._delivery_record(outcome))
                outcomes[task.id] = outcome
                done += 1
                acc = "-" if outcome.accuracy is None else outcome.accuracy
                step = "-" if outcome.step_score is None else f"{outcome.step_score:g}/{outcome.step_max}"
                print(
                    f"[{done}/{total}] {task.id} {outcome.status} "
                    f"acc={acc} step={step} tokens={outcome.tokens} "
                    f"{outcome.duration_s:.1f}s"
                )

        wall_seconds = round(time.perf_counter() - t0, 2)
        ordered = [outcomes[task.id] for task in tasks]
        self._case_records = {}
        case_summaries = self._summarize_cases(tasks, ordered, cases)

        delivery_paths: list[Path] = []
        try:
            delivery_paths = write_delivery_by_domain(
                self.delivery_dir,
                self.config.batch,
                list(self._case_records.values()),
                readable_dir=(
                    self.output_dir / "readable"
                    if self.config.readable_delivery
                    else None
                ),
            )
        except (OSError, ValueError) as exc:
            print(f"[warn] delivery JSONL not written: {exc}")

        path_by_slug = {
            path.stem.split("_")[1]: path
            for path in delivery_paths
            if len(path.stem.split("_")) >= 4
        }
        for item in case_summaries:
            record = self._case_records.get(item["case_id"]) or {}
            slug = DOMAIN_SLUGS.get(str(record.get("domain", "")), "")
            item["delivery_jsonl"] = str(path_by_slug[slug]) if slug in path_by_slug else None

        counts = {
            "success": sum(1 for o in ordered if o.status == "success"),
            "error": sum(1 for o in ordered if o.status == "error"),
            "timeout": sum(1 for o in ordered if o.status == "timeout"),
        }
        valid = [c for c in case_summaries if c["rollouts"]]
        summary = {
            "run_id": self.run_id,
            "started_at": started,
            "finished_at": _now(),
            "wall_seconds": wall_seconds,
            "model": self.model,
            "mock": self.config.mock,
            "use_llm_judge": self.config.use_llm_judge and not self.config.mock,
            "concurrency": self.config.concurrency,
            "timeout_s": self.config.timeout_s,
            "total": total,
            **counts,
            "average_accuracy": round(
                sum(c["correct_rollouts"] for c in valid)
                / max(1, sum(c["rollouts"] for c in valid)),
                6,
            ),
            "average_step_score": round(
                sum(c["average_step_score"] * c["rollouts"] for c in valid)
                / max(1, sum(c["rollouts"] for c in valid)),
                3,
            ),
            "total_tokens": sum(c["total_tokens"] for c in case_summaries),
            "delivery": [str(path) for path in delivery_paths],
            "progress": str(self.progress_path),
            "cases": case_summaries,
            "tasks": [o.model_dump() for o in ordered],
        }
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.run_dir / "report.md").write_text(
            render_batch_report(summary), encoding="utf-8"
        )
        return summary

    def _summarize_cases(
        self,
        tasks: list[TaskSpec],
        outcomes: list[TaskOutcome],
        cases: dict[str, Case],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        case_by_id: dict[str, Case] = {}
        for task, outcome in zip(tasks, outcomes):
            case = cases[task.id]
            case_by_id[case.id] = case
            if not outcome.record_path:
                continue
            try:
                record = json.loads(
                    Path(outcome.record_path).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            if "evaluation" not in record:
                continue
            grouped.setdefault(case.id, []).append(record)

        summaries: list[dict[str, Any]] = []
        for case_id, records in grouped.items():
            records.sort(key=lambda r: int(r.get("rollout_id", 0)))
            case = case_by_id[case_id]
            judge_usage_total = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
            }
            for record in records:
                usage = record.get("judge_usage", {}) or {}
                for key in judge_usage_total:
                    judge_usage_total[key] += int(usage.get(key, 0) or 0)

            result_doc, metrics = summarize_records(
                case=case,
                records=records,
                settings=self.settings,
                client=SimpleNamespace(model=self.model),
                judge_client=SimpleNamespace(model=self.settings.judge_model),
                n_rollouts=len(records),
                use_llm_judge=self.config.use_llm_judge and not self.config.mock,
                judge_usage_total=judge_usage_total,
                elapsed=sum(float(r.get("duration_seconds", 0)) for r in records),
            )
            result_path = self.run_dir / "cases" / f"{case_id}_result.json"
            metrics_path = self.run_dir / "cases" / f"{case_id}_metrics.json"
            report_path = self.run_dir / "cases" / f"{case_id}_report.md"
            result_path.write_text(
                json.dumps(result_doc, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            metrics_path.write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            report_path.write_text(
                render_markdown(case, result_doc, metrics), encoding="utf-8"
            )

            data_item_path: Path | None = None
            try:
                delivery_record = build_delivery_record(
                    case, result_doc, SYSTEM_PROMPT
                )
                issues = validate_delivery_record(
                    delivery_record,
                    expect_rollouts=DEFAULT_ROLLOUTS,
                    strict_model=False,
                )
                for issue in issues:
                    print(f"[warn] {case_id}: {issue}")
                self._case_records[case_id] = delivery_record
                data_item_path = dump_record_json(
                    self.run_dir / "cases" / f"{case_id}_data_item.json",
                    delivery_record,
                )
                n_rollouts = len(delivery_record["rollout_35B_results"])
                if n_rollouts != DEFAULT_ROLLOUTS:
                    print(
                        f"[warn] {case_id}: rollout 数 {n_rollouts}，"
                        f"提交要求为 {DEFAULT_ROLLOUTS}"
                    )
            except ValueError as exc:
                print(f"[warn] {case_id}: 交付记录未生成：{exc}")

            m = metrics["metrics"]
            summaries.append(
                {
                    "case_id": case_id,
                    "rollouts": len(records),
                    "correct_rollouts": m["correct_rollouts"],
                    "average_accuracy": m["average_accuracy"],
                    "average_step_score": m["average_step_score"],
                    "step_score_max": m["step_score_max"],
                    "total_tokens": m["total_tokens"],
                    "total_tool_calls": m["total_tool_calls"],
                    "failed_tool_calls": m["failed_tool_calls"],
                    "termination_counts": m["termination_counts"],
                    "result_path": str(result_path),
                    "metrics_path": str(metrics_path),
                    "report_path": str(report_path),
                    "data_item_path": str(data_item_path) if data_item_path else None,
                }
            )
        return summaries
