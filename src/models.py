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
    rubric_repaired: bool = False
    importance: Importance = "preferred"
    type: QuestionType
    instructions: str
    criteria: list[str] | dict[str, str] | None = None
    target: float | str | bool

    @model_validator(mode="before")
    @classmethod
    def normalize_model_variations(cls, data):
        """Repair provider JSON variations before strict JEV validation."""
        if not isinstance(data, dict):
            return data
        data = data.copy()
        repaired = bool(data.get("rubric_repaired", False))
        if "id" in data:
            data["id"] = str(data["id"]).strip()

        importance = str(data.get("importance", "preferred")).strip().lower()
        if importance in ("required", "must", "must-have", "mandatory"):
            data["importance"] = "required"
        else:
            data["importance"] = "preferred"

        kind = str(data.get("type", "noul")).strip().lower()
        if kind not in ("score", "noul", "choice"):
            kind, repaired = "noul", True
        data["type"] = kind
        criteria = data.get("criteria")
        if isinstance(criteria, str):
            try:
                parsed = json.loads(criteria)
                if isinstance(parsed, (list, dict)):
                    criteria = parsed
            except (ValueError, TypeError):
                pass

        if kind == "score":
            levels = None
            if isinstance(criteria, dict):
                def order(item):
                    try:
                        return (0, float(item[0]))
                    except (TypeError, ValueError):
                        return (1, 0)
                levels = [str(value).strip() for _, value in sorted(criteria.items(), key=order)]
            elif isinstance(criteria, list):
                levels = [str(value).strip() for value in criteria]
            elif isinstance(criteria, str):
                pairs = re.findall(
                    r"(?:^|[,;|\n]\s*)(\d+)\s*[:.)-]\s*(.*?)(?=[,;|\n]\s*\d+\s*[:.)-]|$)",
                    criteria,
                )
                if pairs:
                    levels = [description.strip() for _, description in sorted(pairs, key=lambda x: int(x[0]))]
                else:
                    split = [re.sub(r"^[-•*]\s*", "", part).strip()
                             for part in re.split(r"[;|\n]+", criteria)]
                    levels = [part for part in split if part]
            levels = [level for level in (levels or []) if level]
            if len(levels) > 10:
                levels, repaired = levels[:9] + [levels[-1]], True
            if len(levels) < 2:
                levels = [
                    "No relevant evidence in the resume.",
                    "Minimal exposure; does not meet the stated requirement.",
                    "Some relevant evidence, but substantial gaps remain.",
                    "Mostly meets the requirement with a minor gap.",
                    "Meets the requirement with clear resume evidence.",
                    "Exceeds the requirement with strong, specific evidence.",
                ]
                data["target"], repaired = 4, True
            data["criteria"] = levels
            target = data.get("target")
            try:
                if isinstance(target, bool):
                    raise ValueError
                numeric_target = float(target)
                if not 0 <= numeric_target <= len(levels) - 1:
                    numeric_target, repaired = min(max(numeric_target, 0), len(levels) - 1), True
                data["target"] = numeric_target
            except (TypeError, ValueError):
                data["target"], repaired = min(4, len(levels) - 1), True

        elif kind == "noul":
            if isinstance(criteria, str):
                pairs = re.findall(
                    r"(?:^|[,;|\n]\s*)(true|false)\s*:\s*(.*?)(?=[,;|\n]\s*(?:true|false)\s*:|$)",
                    criteria,
                    flags=re.IGNORECASE,
                )
                criteria = {key.lower(): description.strip() for key, description in pairs} or None
            data["criteria"] = criteria if isinstance(criteria, dict) else None
            target = data.get("target")
            if isinstance(target, str):
                target = target.strip().lower() in ("true", "yes", "1")
            data["target"] = True if target is None else bool(target)

        else:  # choice
            if isinstance(criteria, list):
                criteria = {str(value): str(value) for value in criteria}
            elif isinstance(criteria, str):
                pairs = re.findall(
                    r"(?:^|[,;|\n]\s*)([A-Za-z][\w-]*)\s*:\s*(.*?)(?=[,;|\n]\s*[A-Za-z][\w-]*\s*:|$)",
                    criteria,
                )
                criteria = {key: description.strip() for key, description in pairs}
            if not isinstance(criteria, dict) or len(criteria) < 2:
                criteria = {
                    "meets_requirement": "The resume demonstrates the stated requirement.",
                    "does_not_meet": "The resume does not demonstrate the stated requirement.",
                }
                data["target"], repaired = "meets_requirement", True
            data["criteria"] = {str(key): str(value) for key, value in criteria.items()}
            target = str(data.get("target", ""))
            if target not in data["criteria"]:
                by_lower = {key.lower(): key for key in data["criteria"]}
                data["target"] = by_lower.get(target.lower(), next(iter(data["criteria"])))
                repaired = True

        data["rubric_repaired"] = repaired
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
