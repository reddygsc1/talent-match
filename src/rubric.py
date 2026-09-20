import re
from typing import Any

from .models import Requirement
from .pipeline import RubricError

DASH = " — "


def requirements_to_rows(requirements: list[Requirement]) -> list[dict[str, Any]]:
    rows = []
    for requirement in requirements:
        if requirement.type == "score":
            criteria = "\n".join(f"{i}{DASH}{text}" for i, text in enumerate(requirement.criteria))
            index = int(float(requirement.target))
            target = f"{index}{DASH}{requirement.criteria[index]}"
        elif requirement.type == "choice":
            criteria = "\n".join(f"{key}{DASH}{description}" for key, description in requirement.criteria.items())
            target = str(requirement.target)
        else:
            mapping = requirement.criteria if isinstance(requirement.criteria, dict) else {}
            criteria = "\n".join([
                f"Yes{DASH}{mapping.get('true', 'Requirement is demonstrated')}",
                f"No{DASH}{mapping.get('false', 'Requirement is not demonstrated')}",
            ])
            target = "Yes" if requirement.target else "No"
        rows.append({
            "ID": requirement.id,
            "Requirement": requirement.name,
            "JD wording": requirement.jd_excerpt,
            "Importance": requirement.importance.title(),
            "Type": requirement.type.title(),
            "Expected": target,
            "Evaluation question": requirement.instructions,
            "Criteria (one per line)": criteria,
            "Source verified": requirement.source_verified,
            "Auto-repaired": requirement.rubric_repaired,
        })
    return rows


def rows_to_requirements(rows: list[dict[str, Any]]) -> list[Requirement]:
    requirements = []
    errors = []
    for index, row in enumerate(rows):
        try:
            kind = str(row.get("Type", "noul")).strip().lower()
            criteria_text = str(row.get("Criteria (one per line)", ""))
            lines = [line.strip() for line in criteria_text.splitlines() if line.strip()]
            if kind == "score":
                criteria = [_description(line) for line in lines]
                expected = str(row.get("Expected", ""))
                match = re.match(r"\s*(\d+(?:\.\d+)?)", expected)
                if match:
                    target: float | str | bool = float(match.group(1))
                else:
                    labels = {label.casefold(): i for i, label in enumerate(criteria)}
                    target = labels.get(expected.strip().casefold(), 4)
            elif kind == "choice":
                criteria = dict(_pair(line) for line in lines)
                target = str(row.get("Expected", "")).strip()
            else:
                pairs = dict(_pair(line) for line in lines)
                criteria = {
                    "true": pairs.get("Yes", pairs.get("true", "Requirement is demonstrated")),
                    "false": pairs.get("No", pairs.get("false", "Requirement is not demonstrated")),
                }
                target = str(row.get("Expected", "Yes")).strip().lower() in ("yes", "true", "1")
            requirements.append(Requirement(
                id=str(row.get("ID") or f"requirement_{index + 1}").strip(),
                name=str(row.get("Requirement", "")).strip(),
                jd_excerpt=str(row.get("JD wording", "")).strip(),
                source_verified=bool(row.get("Source verified", False)),
                rubric_repaired=bool(row.get("Auto-repaired", False)),
                importance=str(row.get("Importance", "Preferred")).lower(),
                type=kind,
                instructions=str(row.get("Evaluation question", "")).strip(),
                criteria=criteria,
                target=target,
            ))
        except Exception as exc:
            errors.append(f"row {index + 1}: {exc}")
    if errors:
        raise RubricError("Could not read rubric table: " + "; ".join(errors))
    if not requirements:
        raise RubricError("Add at least one rubric requirement.")
    ids = [requirement.id for requirement in requirements]
    if len(ids) != len(set(ids)):
        raise RubricError("Requirement IDs must be unique.")
    return requirements


def _description(line: str) -> str:
    return _pair(line)[1]


def _pair(line: str) -> tuple[str, str]:
    for separator in (DASH, " - ", ":"):
        if separator in line:
            key, value = line.split(separator, 1)
            return key.strip(), value.strip()
    return line.strip(), line.strip()
