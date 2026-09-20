from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["score", "noul", "choice"]
Importance = Literal["required", "preferred"]
Verdict = Literal["Match", "Needs improvement — Gaps", "No match"]


class Requirement(BaseModel):
    id: str
    name: str
    jd_excerpt: str
    importance: Importance = "preferred"
    type: QuestionType
    instructions: str
    criteria: list[str] | dict[str, str] | None = None
    target: float | str | bool

    @model_validator(mode="after")
    def validate_criteria(self):
        if self.type == "score" and not isinstance(self.criteria, list):
            raise ValueError("Score requirements need an ordered criteria list")
        if self.type == "choice" and not isinstance(self.criteria, dict):
            raise ValueError("Choice requirements need an option map")
        return self

    @property
    def weight(self) -> int:
        return 2 if self.importance == "required" else 1


class Evidence(BaseModel):
    quote: str | None = None
    location: str | None = None
    status: Literal["sufficient", "partial", "missing"] = "missing"


class Evaluation(BaseModel):
    requirement_id: str
    value: float | str | bool | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: Evidence = Field(default_factory=Evidence)
    gap: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class Result(BaseModel):
    requirement: Requirement
    evaluation: Evaluation
    verdict: Verdict
    points: int | None


class Summary(BaseModel):
    fit_score: float | None
    coverage: float
    label: str
