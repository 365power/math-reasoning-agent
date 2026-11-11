from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from ..config import CASE_DIR, PROJECT_ROOT
    from .engine import RunConfig, Scheduler
    from .tasks import expand_case, load_tasks
else:  # 兼容直接执行本文件：python agent_project/scheduler/cli.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agent_project.config import CASE_DIR, PROJECT_ROOT
    from agent_project.scheduler.engine import RunConfig, Scheduler
    from agent_project.scheduler.tasks import expand_case, load_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="数学 Agent 调度器：把多个 rollout 拆成独立 worker 子进程并发执行"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--input",
        type=Path,
        help="任务清单（JSONL 或 JSON 数组），每行一个任务",
    )
    source.add_argument(
        "--case",
        type=Path,
        help="题目 JSON 路径；与 --rollouts 一起使用时自动展开为多个任务",
    )
    source.add_argument(
        "--cases-dir",
        type=Path,
        help="题目目录：目录下每个 *.json 按 --rollouts 展开成任务",
    )
    parser.add_argument(
        "--rollouts",
        type=int,
        default=8,
        help="配合 --case / --cases-dir 使用，每题展开成多少个 rollout（默认 8）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "scheduler",
        help="调度器输出根目录",
    )
    parser.add_argument("--batch", default="batch01", help="交付 JSONL 文件名（不含后缀）")
    parser.add_argument("--run-id", default="", help="本次运行的 id，默认用时间戳")
    parser.add_argument("--concurrency", type=int, default=4, help="并发 worker 数")
    parser.add_argument("--timeout", type=float, default=1800.0, help="单个任务超时秒数")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个任务（0 表示全部）")
    parser.add_argument("--model", default=None, help="覆盖 DEEPSEEK_MODEL")
    parser.add_argument("--mock", action="store_true", help="不调用 API，用脚本化模型跑通调度")
    parser.add_argument(
        "--no-llm-judge",
        action="store_true",
        help="使用启发式评分，不调用评分模型",
    )
    parser.add_argument(
        "--readable-delivery",
        action="store_true",
        help="同时输出缩进排版的可读副本（正式交付仍是一行一条 JSONL）",
    )
    return parser.parse_args()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    if args.input:
        tasks = load_tasks(args.input)
    elif args.cases_dir:
        if args.rollouts < 1:
            print("--rollouts 必须 >= 1", file=sys.stderr)
            return 2
        if not args.cases_dir.is_dir():
            print(f"题目目录不存在：{args.cases_dir}", file=sys.stderr)
            return 2
        case_paths = sorted(args.cases_dir.glob("*.json"))
        case_paths += sorted(
            path
            for path in args.cases_dir.rglob("case.json")
            if path.parent != args.cases_dir
        )
        case_paths = sorted(set(case_paths))
        if not case_paths:
            print(f"目录中没有 *.json 题目：{args.cases_dir}", file=sys.stderr)
            return 2
        tasks = []
        try:
            for case_path in case_paths:
                tasks.extend(expand_case(case_path, args.rollouts))
        except ValueError as exc:
            print(f"题目加载失败：{exc}", file=sys.stderr)
            return 2
    elif args.case:
        if args.rollouts < 1:
            print("--rollouts 必须 >= 1", file=sys.stderr)
            return 2
        tasks = expand_case(args.case, args.rollouts)
    else:
        tasks = expand_case(
            CASE_DIR / "math_001_arctan_series" / "case.json", max(1, args.rollouts)
        )

    if args.limit and args.limit > 0:
        tasks = tasks[: args.limit]

    config = RunConfig(
        output_dir=args.output_dir,
        batch=args.batch,
        run_id=args.run_id,
        concurrency=max(1, args.concurrency),
        timeout_s=args.timeout,
        mock=args.mock,
        use_llm_judge=not args.no_llm_judge,
        model=args.model,
        limit=args.limit,
        readable_delivery=args.readable_delivery,
    )

    scheduler = Scheduler(config)
    try:
        summary = scheduler.run(tasks)
    except (ValueError, RuntimeError) as exc:
        print(f"调度失败：{exc}", file=sys.stderr)
        return 2

    print("")
    print("=" * 60)
    print(f"run_id            : {summary['run_id']}")
    print(f"tasks             : {summary['total']}（{summary['success']} 成功 / "
          f"{summary['error']} 失败 / {summary['timeout']} 超时）")
    print(f"average_accuracy  : {summary['average_accuracy']}")
    print(f"average_step_score: {summary['average_step_score']}")
    print(f"total_tokens      : {summary['total_tokens']}")
    print(f"wall_seconds      : {summary['wall_seconds']}")
    print(f"progress          : {summary['progress']}")
    delivery = summary.get("delivery") or []
    if delivery:
        for path in delivery:
            print(f"delivery          : {path}")
    else:
        print("delivery          : （未生成，见上方警告）")
    print(f"report            : {scheduler.run_dir / 'report.md'}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
