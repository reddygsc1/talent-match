import json
import re
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["score", "noul", "choice"]
Importance = Literal["required", "preferred"]
Verdict = Literal["Match", "Needs improvement — Gaps", "No match"]


class Requirement(BaseModel):
    id: str
    name: str
    jd_excerpt: str
    source_verified: bool = True
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
        if "id" in data:
            data["id"] = str(data["id"]).strip()
        if isinstance(data.get("importance"), str):
            data["importance"] = data["importance"].strip().lower().replace("must-have", "required").replace("nice-to-have", "preferred")
        if isinstance(data.get("type"), str):
            data["type"] = data["type"].strip().lower()
        criteria = data.get("criteria")
        if isinstance(criteria, str):
            try:
                parsed = json.loads(criteria)
                if isinstance(parsed, (list, dict)):
                    criteria = data["criteria"] = parsed
            except (ValueError, TypeError):
                pass
        if data.get("type") == "score" and isinstance(criteria, str):
            pairs = re.findall(r"(?:^|,\s*)(\d+)\s*:\s*(.*?)(?=,\s*\d+\s*:|$)", criteria)
            if pairs:
                levels = [description.strip() for _, description in sorted(pairs, key=lambda x: int(x[0]))]
                if len(levels) > 10:
                    old_target = data.get("target")
                    data["target"] = min(float(old_target), 9) if str(old_target).replace(".", "", 1).isdigit() else old_target
                    levels = levels[:9] + [levels[-1]]
                data["criteria"] = criteria = levels
        elif data.get("type") in ("noul", "choice") and isinstance(criteria, str):
            pairs = re.findall(r"(?:^|,\s*)([A-Za-z][\w-]*)\s*:\s*(.*?)(?=,\s*[A-Za-z][\w-]*\s*:|$)", criteria)
            if pairs:
                data["criteria"] = criteria = {key: description.strip() for key, description in pairs}
        if data.get("type") == "score" and isinstance(criteria, dict):
            # Models sometimes emit {"0": "None", "1": "Basic"} instead of an array.
            def order(item):
                try:
                    return (0, float(item[0]))
                except (TypeError, ValueError):
                    return (1, 0)
            levels = [str(value) for _, value in sorted(criteria.items(), key=order)]
            data["criteria"] = levels[:9] + [levels[-1]] if len(levels) > 10 else levels
        elif data.get("type") == "choice" and isinstance(criteria, list):
            # A list is usable as choices when descriptions were omitted.
            data["criteria"] = {str(value): str(value) for value in criteria}
        target = data.get("target")
        if data.get("type") == "score" and isinstance(target, str):
            try:
                data["target"] = float(target)
            except ValueError:
                pass
        elif data.get("type") == "noul":
            if target is None:
                data["target"] = True
            elif isinstance(target, str):
                if target.strip().lower() in ("true", "yes"):
                    data["target"] = True
                elif target.strip().lower() in ("false", "no"):
                    data["target"] = False
        return data

    @model_validator(mode="after")
    def validate_criteria(self):
        if not self.id or not self.name.strip() or not self.instructions.strip():
            raise ValueError("Requirement id, name, and instructions cannot be empty")
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

    @model_validator(mode="before")
    @classmethod
    def normalize_model_variations(cls, data):
        if isinstance(data, str):
            text = data.strip()
            return {"quote": text or None, "status": "sufficient" if text else "missing"}
        if not isinstance(data, dict):
            return {"status": "missing"}
        data = data.copy()
        if "quote" not in data:
            data["quote"] = data.get("text") or data.get("excerpt")
        status = str(data.get("status", "missing")).strip().lower().replace("found", "sufficient")
        if status in ("none", "not_found", "not found", "unknown"):
            status = "missing"
        data["status"] = status if status in ("sufficient", "partial", "missing") else "missing"
        return data


class Evaluation(BaseModel):
    requirement_id: str
    value: float | str | bool | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: Evidence = Field(default_factory=Evidence)
    gap: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_model_variations(cls, data):
        if not isinstance(data, dict):
            return data
        data = data.copy()
        if "requirement_id" not in data and "id" in data:
            data["requirement_id"] = data["id"]
        evidence = data.get("evidence")
        if evidence is None:
            data["evidence"] = {"status": "missing"}
        raw = data.get("raw")
        if isinstance(raw, str):
            data["raw"] = {"model_output": raw}
        elif raw is None:
            data["raw"] = {}
        confidence = data.get("confidence")
        if isinstance(confidence, str):
            try:
                confidence = float(confidence.rstrip("%"))
                data["confidence"] = confidence
            except ValueError:
                data["confidence"] = None
        if isinstance(confidence, (int, float)) and 1 < confidence <= 100:
            data["confidence"] = confidence / 100
        if data.get("gap") is None:
            data["gap"] = ""
        elif isinstance(data.get("gap"), list):
            data["gap"] = "; ".join(str(x) for x in data["gap"])
        elif not isinstance(data.get("gap"), str):
            data["gap"] = str(data["gap"])
        return data


class Result(BaseModel):
    requirement: Requirement
    evaluation: Evaluation
    verdict: Verdict
    points: int | None


class Summary(BaseModel):
    fit_score: float | None
    coverage: float
    label: str
