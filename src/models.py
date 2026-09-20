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

    @model_validator(mode="before")
    @classmethod
    def normalize_model_variations(cls, data):
        """Accept common JSON variations while retaining JEV's required shapes."""
        if not isinstance(data, dict):
            return data
        data = data.copy()
        criteria = data.get("criteria")
        if data.get("type") == "score" and isinstance(criteria, dict):
            # Models sometimes emit {"0": "None", "1": "Basic"} instead of an array.
            def order(item):
                try:
                    return (0, float(item[0]))
                except (TypeError, ValueError):
                    return (1, 0)
            data["criteria"] = [str(value) for _, value in sorted(criteria.items(), key=order)]
        elif data.get("type") == "choice" and isinstance(criteria, list):
            # A list is usable as choices when descriptions were omitted.
            data["criteria"] = {str(value): str(value) for value in criteria}
        return data

    @model_validator(mode="after")
    def validate_criteria(self):
        if self.type == "score":
            if not isinstance(self.criteria, list) or not 2 <= len(self.criteria) <= 10:
                raise ValueError("Score requirements need 2–10 ordered criteria levels")
            if isinstance(self.target, bool) or not isinstance(self.target, (int, float)):
                raise ValueError("A score target must be a numeric 0-based level")
            if not 0 <= float(self.target) <= len(self.criteria) - 1:
                raise ValueError(
                    f"Score target must be between 0 and {len(self.criteria) - 1}; "
                    "use the level index, not years or a percentage"
                )
        if self.type == "choice":
            if not isinstance(self.criteria, dict) or len(self.criteria) < 2:
                raise ValueError("Choice requirements need at least two options")
            if str(self.target) not in self.criteria:
                raise ValueError("Choice target must be one of the option keys")
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
