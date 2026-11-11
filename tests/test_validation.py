from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_project.case import Case
from agent_project.config import CASE_DIR, Settings
from agent_project.integrate import (
    build_delivery_record,
    dumps_record,
    write_jsonl,
)
from agent_project.llm import MockLLMClient
from agent_project.runner import run_case
from agent_project.validation import (
    DELIVERY_FIELDS,
    has_errors,
    validate_case_payload,
    validate_delivery_record,
    validate_jsonl,
)


class TestLayerOneInput(unittest.TestCase):
    def setUp(self) -> None:
        self.case = Case.load(CASE_DIR / "math_001_arctan_series" / "case.json")

    def test_valid_case_passes(self) -> None:
        issues = validate_case_payload(self.case.to_dict(), location="case")
        self.assertFalse(has_errors(issues), [str(issue) for issue in issues])

    def test_old_field_name_is_rejected(self) -> None:
        payload = self.case.to_dict()
        payload["designation_rationale"] = payload.pop("design_rationale")
        codes = {issue.code for issue in validate_case_payload(payload)}
        self.assertIn("field.old_name", codes)
        self.assertIn("field.missing", codes)

    def test_chinese_question_is_rejected(self) -> None:
        payload = self.case.to_dict()
        payload["question"] = "求该级数的和。"
        issues = validate_case_payload(payload)
        self.assertTrue(has_errors(issues))
        self.assertTrue(any(issue.code == "english" for issue in issues))

    def test_vague_evidence_location_is_rejected(self) -> None:
        payload = self.case.to_dict()
        payload["evidence"][0]["location"] = "somewhere in the book"
        issues = validate_case_payload(payload)
        self.assertTrue(any(issue.code == "evidence.locator" for issue in issues))


class TestLayerTwoDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = Settings.from_env()
        case = Case.load(CASE_DIR / "math_001_arctan_series" / "case.json")
        client = MockLLMClient()
        result, _ = run_case(
            settings=settings,
            case=case,
            client=client,
            judge_client=client,
            rollouts=1,
            use_llm_judge=False,
        )
        cls.record = build_delivery_record(case, result)
        cls.case = case

    def test_record_uses_spec_field_names(self) -> None:
        self.assertEqual(tuple(self.record), DELIVERY_FIELDS)
        self.assertIn("design_rationale", self.record)
        self.assertNotIn("designation_rationale", self.record)
        self.assertIsInstance(self.record["trajectory"], list)
        rollout = self.record["rollout_35B_results"][0]
        self.assertIn("answer-level_accuracy", rollout)
        self.assertIn("step-level_score", rollout)
        self.assertNotIn("evaluation", rollout)

    def test_record_passes_layer_two(self) -> None:
        issues = validate_delivery_record(
            self.record, expect_rollouts=0, strict_model=False
        )
        self.assertFalse(has_errors(issues), [str(issue) for issue in issues])

    def test_jsonl_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch01_math_1_20261110.jsonl"
            write_jsonl(path, [self.record])
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", raw)
            self.assertEqual(raw.count(b"\n"), 1)
            issues = validate_jsonl(
                path, expect_rollouts=0, strict_model=False
            )
            self.assertFalse(has_errors(issues), [str(issue) for issue in issues])

    def test_bom_and_crlf_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch01_math_1_20261110.jsonl"
            line = dumps_record(self.record)
            path.write_bytes(b"\xef\xbb\xbf" + line.encode("utf-8") + b"\r\n")
            codes = {
                issue.code
                for issue in validate_jsonl(
                    path, expect_rollouts=0, strict_model=False
                )
            }
            self.assertIn("jsonl.bom", codes)
            self.assertIn("jsonl.newline", codes)

    def test_missing_rollouts_fail(self) -> None:
        payload = json.loads(json.dumps(self.record))
        payload["rollout_35B_results"][0].pop("answer-level_accuracy")
        issues = validate_delivery_record(
            payload, expect_rollouts=1, strict_model=False
        )
        self.assertTrue(any(issue.code == "rollout.missing_field" for issue in issues))


if __name__ == "__main__":
    unittest.main()
