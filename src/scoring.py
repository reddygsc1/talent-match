from .models import Evaluation, Requirement, Result, Summary


def classify(requirement: Requirement, evaluation: Evaluation) -> Result:
    value, evidence = evaluation.value, evaluation.evidence.status
    if value is None or evidence == "missing":
        return Result(requirement=requirement, evaluation=evaluation,
                      verdict="Needs improvement — Gaps", points=None)

    try:
        if requirement.type == "score":
            target = float(requirement.target)
            actual = float(value)
            if actual >= target:
                verdict, points = "Match", 100
            elif actual >= max(0, target - 1):
                verdict, points = "Needs improvement — Gaps", 50
            else:
                verdict, points = "No match", 0
        elif requirement.type == "noul":
            probability = float(value)
            if not 0 <= probability <= 1:
                raise ValueError("Noul probability is outside 0–1")
            expected = bool(requirement.target)
            agreement = probability if expected else 1 - probability
            if agreement >= .75:
                verdict, points = "Match", 100
            elif agreement >= .35:
                verdict, points = "Needs improvement — Gaps", 50
            else:
                verdict, points = "No match", 0
        else:
            if value == requirement.target:
                verdict, points = "Match", 100
            elif value in ("other", "unclear", "none"):
                verdict, points = "Needs improvement — Gaps", 50
            else:
                verdict, points = "No match", 0
    except (TypeError, ValueError, OverflowError):
        evaluation.value = None
        evaluation.evidence.status = "missing"
        evaluation.gap = evaluation.gap or "The evaluator returned an invalid value for this requirement."
        return Result(requirement=requirement, evaluation=evaluation,
                      verdict="Needs improvement — Gaps", points=None)

    if evidence == "partial" and verdict == "Match":
        verdict, points = "Needs improvement — Gaps", 50
    return Result(requirement=requirement, evaluation=evaluation,
                  verdict=verdict, points=points)


def summarize(results: list[Result]) -> Summary:
    total_weight = sum(r.requirement.weight for r in results)
    scored = [r for r in results if r.points is not None]
    scored_weight = sum(r.requirement.weight for r in scored)
    coverage = (100 * scored_weight / total_weight) if total_weight else 0
    fit = (sum(r.points * r.requirement.weight for r in scored) / scored_weight
           if scored_weight else None)

    required_failure = any(
        r.requirement.importance == "required" and r.verdict != "Match"
        for r in results
    )
    if fit is None:
        label = "Insufficient evidence"
    elif fit >= 80 and coverage >= 80 and not required_failure:
        label = "Match"
    elif fit < 50 and coverage >= 80:
        label = "No match"
    else:
        label = "Needs improvement — Gaps"
    return Summary(fit_score=round(fit, 1) if fit is not None else None,
                   coverage=round(coverage, 1), label=label)
