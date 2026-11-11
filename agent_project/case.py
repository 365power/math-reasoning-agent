from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_DOMAINS = {"Mathematics", "Physics", "Chemistry", "Biology"}
_CJK = re.compile(r"[一-鿿]")
_LOCATOR = re.compile(
    r"(?i)(?:\bpage\b|\bpp?\.|\bsection\b|§|\beq(?:uation)?\b|\beq\.|\bchapter\b|"
    r"\bch\.|\bproblem\b|\bexercise\b|\bparagraph\b|¶|\bappendix\b|\btable\b|"
    r"\bfigure\b|\bexample\b)\s*[\w.\-()]*|\d"
)


def contains_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def is_specific_location(value: str) -> bool:
    return bool(_LOCATOR.search(value or ""))


def _require_english(value: str, field_name: str) -> str:
    if contains_cjk(value):
        raise ValueError(f"{field_name} must be written in English (CJK characters found)")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RubricCriterion(StrictModel):
    criterion_id: int = Field(ge=1)
    description: str = Field(min_length=1)
    points: int = Field(ge=0)

    @field_validator("description")
    @classmethod
    def english(cls, value: str) -> str:
        return _require_english(value, "rubric.criteria.description")


class Rubric(StrictModel):
    total_points: int = Field(gt=0)
    criteria: list[RubricCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def check_points(self) -> "Rubric":
        if self.total_points != 10:
            raise ValueError("rubric.total_points must be 10")
        if sum(c.points for c in self.criteria) != self.total_points:
            raise ValueError(
                "the sum of rubric.criteria points must equal total_points"
            )
        return self


class Evidence(StrictModel):
    source: str = Field(min_length=1)
    location: str = Field(min_length=1)
    content: str = Field(min_length=1)

    @field_validator("source", "content")
    @classmethod
    def english(cls, value: str) -> str:
        return _require_english(value, "evidence")

    @model_validator(mode="after")
    def check_location(self) -> "Evidence":
        if not _LOCATOR.search(self.location):
            raise ValueError(
                "evidence.location must name a concrete locator "
                "(page, section, equation, problem number, paragraph, etc.)"
            )
        return self


class ScoringMethod(StrictModel):
    method: str = Field(min_length=1)
    description: str = Field(min_length=1)
    max_score: int = Field(gt=0)

    @field_validator("description")
    @classmethod
    def english(cls, value: str) -> str:
        return _require_english(value, "scoring_method.description")

    @model_validator(mode="after")
    def check_max_score(self) -> "ScoringMethod":
        if self.max_score != 10:
            raise ValueError("scoring_method.max_score must be 10")
        return self


class HumanReview(StrictModel):
    status: str = Field(min_length=1)
    review_result: str = ""
    modification: str = ""

    @field_validator("review_result", "modification")
    @classmethod
    def english(cls, value: str) -> str:
        return _require_english(value, "human_review")


class Case(StrictModel):
    """Strict input schema for the scientific-reasoning delivery spec (section 6.1)."""

    id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_url: str = ""
    domain: str = Field(min_length=1)
    subdomain: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    context: str | None = None
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    rubric: Rubric
    design_rationale: str = Field(min_length=1)
    solution_steps: list[str] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    scoring_method: ScoringMethod
    human_review: HumanReview

    @field_validator("source_title", "subdomain", "context", "question", "answer")
    @classmethod
    def english(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_english(value, "case text")

    @field_validator("solution_steps")
    @classmethod
    def english_steps(cls, value: list[str]) -> list[str]:
        for step in value:
            _require_english(step, "solution_steps")
        return value

    @field_validator("design_rationale")
    @classmethod
    def english_rationale(cls, value: str) -> str:
        return _require_english(value, "design_rationale")

    @model_validator(mode="after")
    def check_domain(self) -> "Case":
        if self.domain not in ALLOWED_DOMAINS:
            raise ValueError(
                f"domain must be one of {sorted(ALLOWED_DOMAINS)}, got {self.domain!r}"
            )
        return self

    @classmethod
    def load(cls, path: str | Path) -> "Case":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(raw)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
