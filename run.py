from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from agent_project.case import Case
from agent_project.clients import build_clients
from agent_project.config import CASE_DIR, OUTPUT_DIR, Settings
from agent_project.integrate import (
    DEFAULT_ROLLOUTS,
    build_delivery_record,
    delivery_filename,
    dump_record_json,
    write_jsonl,
)
from agent_project.report import render_markdown
from agent_project.runner import SYSTEM_PROMPT, run_case
from agent_project.validation import validate_delivery_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="考研数学推理 Agent 评测流水线")
    parser.add_argument(
        "--case",
        type=Path,
        default=CASE_DIR / "math_001_arctan_series" / "case.json",
        help="6.1 格式的题目 JSON 路径",
    )
    parser.add_argument(
        "--rollouts",
        type=int,
        default=None,
        help="rollout 次数，默认读取 ROLLOUTS 或 8",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="输出目录",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="不调用 API，用脚本化模型跑通整条流水线",
    )
    parser.add_argument(
        "--no-llm-judge",
        action="store_true",
        help="使用启发式评分，不调用评分模型",
    )
    parser.add_argument(
        "--batch",
        default="batch01",
        help="交付 JSONL 的批次名（默认 batch01）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings.from_env()

    try:
        case = Case.load(args.case)
    except Exception as exc:  # noqa: BLE001
        print(f"题目文件加载失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.rollouts is not None:
        if args.rollouts < 1:
            print("--rollouts 必须 >= 1", file=sys.stderr)
            return 2
        settings = replace(settings, rollouts=args.rollouts)

    if not args.mock and not settings.has_api_key:
        print(
            "未检测到 DEEPSEEK_API_KEY。\n"
            "请复制 .env.example 为 .env，填入密钥；"
            "或先运行 `python run.py --mock` 验证流水线。",
            file=sys.stderr,
        )
        return 2

    if args.mock:
        print("模式：mock（不调用 API）")
    else:
        print(f"模式：API（model={settings.model}, base_url={settings.base_url}）")

    client, judge_client, use_llm_judge = build_clients(
        settings, args.mock, not args.no_llm_judge
    )

    if not args.no_llm_judge and not args.mock:
        print("工具警告：python 工具会在本机执行模型生成的代码，请只在隔离环境中运行。")

    result_doc, metrics = run_case(
        settings=settings,
        case=case,
        client=client,
        judge_client=judge_client,
        rollouts=args.rollouts,
        use_llm_judge=use_llm_judge,
        progress=lambda msg: print(msg, flush=True),
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = case.id
    result_path = out_dir / f"{stem}_result.json"
    metrics_path = out_dir / f"{stem}_metrics.json"
    report_path = out_dir / f"{stem}_report.md"

    result_path.write_text(
        json.dumps(result_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(
        render_markdown(case, result_doc, metrics), encoding="utf-8"
    )

    data_item_path = None
    jsonl_path = None
    try:
        record = build_delivery_record(case, result_doc, SYSTEM_PROMPT)
        issues = validate_delivery_record(
            record, expect_rollouts=DEFAULT_ROLLOUTS, strict_model=False
        )
        for issue in issues:
            print(f"交付校验 {issue}", file=sys.stderr)
        data_item_path = dump_record_json(out_dir / f"{stem}_data_item.json", record)
        jsonl_path = write_jsonl(
            out_dir / delivery_filename(args.batch, case.domain, 1), [record]
        )
    except ValueError as exc:
        print(f"警告：交付记录未生成：{exc}", file=sys.stderr)

    m = metrics["metrics"]
    print("")
    print("=" * 60)
    print(f"average_accuracy : {m['average_accuracy']}")
    print(f"average_step_score: {m['average_step_score']}/{m['step_score_max']}")
    print(f"total_tokens      : {m['total_tokens']}")
    print(f"tool calls        : {m['total_tool_calls']}（失败 {m['failed_tool_calls']}）")
    print(f"termination       : {m['termination_counts']}")
    print(f"result            : {result_path}")
    print(f"metrics           : {metrics_path}")
    print(f"report            : {report_path}")
    print(f"data_item         : {data_item_path or '（未生成，见上方警告）'}")
    print(f"delivery jsonl    : {jsonl_path or '（未生成，见上方警告）'}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
