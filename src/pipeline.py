import json
from pydantic import ValidationError

from .models import Evaluation, Requirement, Result, Summary
from .scoring import classify, summarize


class RubricError(ValueError):
    pass


def parse_rubric(text: str) -> list[Requirement]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RubricError(f"Rubric JSON is invalid near line {exc.lineno}, column {exc.colno}.") from exc
    if not isinstance(data, list) or not data:
        raise RubricError("Rubric must be a non-empty JSON list of requirements.")
    requirements = []
    errors = []
    for index, item in enumerate(data):
        try:
            requirements.append(Requirement.model_validate(item))
        except (ValidationError, TypeError, ValueError) as exc:
            message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            errors.append(f"requirement {index + 1}: {message}")
    if errors:
        raise RubricError("; ".join(errors))
    ids = [r.id for r in requirements]
    if len(ids) != len(set(ids)):
        raise RubricError("Requirement IDs must be unique.")
    return requirements


def build_results(requirements: list[Requirement], evaluations: list[Evaluation]) -> tuple[list[Result], Summary]:
    by_id = {evaluation.requirement_id: evaluation for evaluation in evaluations}
    results = []
    for requirement in requirements:
        evaluation = by_id.get(requirement.id) or Evaluation(
            requirement_id=requirement.id,
            gap="No evaluation was returned for this requirement.",
        )
        results.append(classify(requirement, evaluation))
    return results, summarize(results)
