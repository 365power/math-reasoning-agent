from __future__ import annotations

import unittest

from agent_project.case import Case
from agent_project.config import CASE_DIR, Settings
from agent_project.judge import answers_match, extract_boxed, normalize_answer
from agent_project.llm import MockLLMClient
from agent_project.runner import run_case
from agent_project.tools.base import safe_path
from agent_project.tools.python_tool import PythonTool


class TestAnswerUtils(unittest.TestCase):
    def test_extract_boxed_nested(self) -> None:
        text = r"推导结束，故 \boxed{\frac{\pi}{4}}。"
        self.assertEqual(extract_boxed(text), r"\frac{\pi}{4}")

    def test_extract_last_boxed(self) -> None:
        text = r"\boxed{0} 再检查 \boxed{\pi/4}"
        self.assertEqual(extract_boxed(text), r"\pi/4")

    def test_normalize_variants(self) -> None:
        variants = [
            r"\frac{\pi}{4}",
            r"\dfrac{\pi}{4}",
            r"\pi/4",
            r"π/4",
            r"0.785398163397448",
        ]
        for value in variants:
            self.assertEqual(normalize_answer(value), "pi/4", value)

    def test_answers_match(self) -> None:
        self.assertTrue(answers_match(r"\frac{\pi}{4}", r"\pi/4"))
        self.assertFalse(answers_match(r"\frac{\pi}{2}", r"\pi/4"))

    def test_equation_style_boxed_answer(self) -> None:
        variants = [
            r"\displaystyle \sum_{n=1}^{\infty}\arctan\frac1{2n^2}=\frac{\pi}{4}",
            r"\displaystyle \sum_{n=1}^{\infty}\arctan\frac{1}{2n^{2}}=\frac{\pi}{4}",
        ]
        for value in variants:
            self.assertTrue(answers_match(value, r"\frac{\pi}{4}"), value)

    def test_fraction_and_exponent_variants(self) -> None:
        self.assertTrue(answers_match(r"\frac{3}{32}", "3/32"))
        self.assertTrue(answers_match("0.09375", r"\frac{3}{32}"))
        self.assertTrue(
            answers_match(
                r"\frac{46 v_0^{2}}{145 g}", r"\frac{46v_0^2}{145g}"
            )
        )
        self.assertTrue(answers_match(r"46v_0^2/(145g)", r"\frac{46v_0^2}{145g}"))
        self.assertFalse(
            answers_match(r"\frac{45v_0^2}{145g}", r"\frac{46v_0^2}{145g}")
        )


class TestCaseAndTools(unittest.TestCase):
    def test_case_loads(self) -> None:
        case = Case.load(CASE_DIR / "math_001_arctan_series" / "case.json")
        self.assertEqual(case.id, "math_001_arctan_series")
        self.assertEqual(
            sum(c.points for c in case.rubric.criteria),
            case.rubric.total_points,
        )

    def test_safe_path_blocks_traversal(self) -> None:
        workspace = CASE_DIR.parent / "data"
        with self.assertRaises(ValueError):
            safe_path("../cases/math_001_arctan_series/case.json", workspace)

    def test_python_tool_runs(self) -> None:
        tool = PythonTool(CASE_DIR.parent / "data", default_timeout=15)
        output = tool.run("print(1 + 1)", timeout=15)
        self.assertIn("exit_code: 0", output)
        self.assertIn("2", output)

    def test_python_tool_keeps_unicode_intact(self) -> None:
        tool = PythonTool(CASE_DIR.parent / "data", default_timeout=15)
        output = tool.run("print('π θ τ')", timeout=15)
        self.assertIn("π θ τ", output)
        self.assertNotIn("�", output)


class TestMockPipeline(unittest.TestCase):
    def test_mock_end_to_end(self) -> None:
        settings = Settings.from_env()
        case = Case.load(CASE_DIR / "math_001_arctan_series" / "case.json")
        client = MockLLMClient()

        result, metrics = run_case(
            settings=settings,
            case=case,
            client=client,
            judge_client=client,
            rollouts=1,
            use_llm_judge=False,
        )

        self.assertEqual(result["average_accuracy"], 1.0)
        self.assertEqual(len(result["rollout_35B_results"]), 1)
        record = result["rollout_35B_results"][0]
        for key in (
            "extracted_answer",
            "evaluation",
            "usage",
            "tool_statistics",
            "termination",
            "messages",
            "tools",
        ):
            self.assertIn(key, record)
        self.assertGreaterEqual(record["tool_statistics"]["total_tool_calls"], 1)
        self.assertEqual(record["evaluation"]["step_level_score"], 10)
        self.assertGreater(metrics["metrics"]["total_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
