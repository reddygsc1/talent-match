import json
import pytest

from src.clients import _validate_evaluations
from src.models import Evaluation, Evidence, Requirement
from src.pipeline import RubricError, build_results, parse_rubric


def score_req(identifier="depth"):
    return Requirement(id=identifier, name="Technical depth", jd_excerpt="technical depth",
        importance="required", type="score", instructions="Rate technical depth",
        criteria=["None", "Basic", "Production", "System ownership"], target=2)


def noul_req(identifier="mentor"):
    return Requirement(id=identifier, name="Mentoring", jd_excerpt="mentor engineers",
        importance="preferred", type="noul", instructions="Is mentoring demonstrated?",
        criteria={"true": "Demonstrated", "false": "Not demonstrated"}, target=True)


def test_malformed_evaluation_does_not_crash_whole_run():
    requirements = [score_req(), noul_req()]
    data = {"evaluations": [
        {"requirement_id": "depth", "value": 2, "evidence": {"quote": "Built APIs", "status": "sufficient"}},
        {"requirement_id": "mentor", "value": {"bad": "shape"}, "evidence": 123},
    ]}
    evaluations = _validate_evaluations(data, "Built APIs", requirements)
    assert len(evaluations) == 2
    assert evaluations[0].value == 2
    assert evaluations[1].value is None
    assert evaluations[1].evidence.status == "missing"


def test_missing_evaluation_is_returned_as_unknown():
    evaluations = _validate_evaluations({"evaluations": []}, "Resume", [score_req()])
    assert len(evaluations) == 1
    assert evaluations[0].value is None
    assert "No evaluation" in evaluations[0].gap


def test_jev_value_cannot_be_changed_by_evidence_model():
    data = {"evaluations": [{"requirement_id": "depth", "value": 0,
        "evidence": {"quote": "Built APIs", "status": "sufficient"}}]}
    evaluations = _validate_evaluations(data, "Built APIs", [score_req()], expected_values={"depth": 2.5})
    assert evaluations[0].value == 2.5


def test_evidence_quote_allows_whitespace_variation_but_rejects_invention():
    valid = {"evaluations": [{"requirement_id": "depth", "value": 2,
        "evidence": {"quote": "Built production APIs", "status": "sufficient"}}]}
    assert _validate_evaluations(valid, "Built   production\nAPIs", [score_req()])[0].value == 2
    invalid = {"evaluations": [{"requirement_id": "depth", "value": 2,
        "evidence": {"quote": "Led an organization", "status": "sufficient"}}]}
    result = _validate_evaluations(invalid, "Built APIs", [score_req()])[0]
    assert result.value is None
    assert result.evidence.status == "missing"


def test_evaluation_aliases_and_nulls_are_normalized():
    evaluation = Evaluation.model_validate({"id": "depth", "value": 2, "confidence": "85%",
        "evidence": {"excerpt": "Built APIs", "status": "found"}, "gap": None, "raw": None})
    assert evaluation.requirement_id == "depth"
    assert evaluation.confidence == .85
    assert evaluation.evidence.quote == "Built APIs"
    assert evaluation.evidence.status == "sufficient"
    assert evaluation.gap == ""


def test_parse_rubric_rejects_non_list_and_duplicate_ids():
    with pytest.raises(RubricError, match="non-empty JSON list"):
        parse_rubric('{"requirements": []}')
    duplicate = [score_req().model_dump(), score_req().model_dump()]
    with pytest.raises(RubricError, match="unique"):
        parse_rubric(json.dumps(duplicate))


def test_build_results_joins_by_id_not_list_position():
    requirements = [score_req(), noul_req()]
    evaluations = [
        Evaluation(requirement_id="mentor", value=.9, evidence=Evidence(quote="Mentored staff", status="sufficient")),
        Evaluation(requirement_id="depth", value=2, evidence=Evidence(quote="Built APIs", status="sufficient")),
    ]
    results, summary = build_results(requirements, evaluations)
    assert [result.requirement.id for result in results] == ["depth", "mentor"]
    assert all(result.verdict == "Match" for result in results)
    assert summary.label == "Match"


def test_invalid_scoring_value_becomes_unknown_not_exception():
    result, _ = build_results([score_req()], [Evaluation(requirement_id="depth", value="not-a-number",
        evidence=Evidence(quote="Something", status="sufficient"))])
    assert result[0].points is None
    assert result[0].verdict == "Needs improvement — Gaps"
