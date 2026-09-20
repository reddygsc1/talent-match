import pytest
from pydantic import ValidationError
from src.clients import JevClient
from src.models import Evidence, Evaluation, Requirement
from src.scoring import classify, summarize


def req(kind="score", target=2, importance="required"):
    criteria = ["none", "basic", "strong", "expert"] if kind == "score" else {"true": "yes", "false": "no"}
    return Requirement(id="depth", name="Depth", jd_excerpt="strong depth", importance=importance,
                       type=kind, instructions="Evaluate depth", criteria=criteria, target=target)


def test_jev_base_url_gets_system_one_path():
    assert JevClient._system_one_url("https://api.typesafe.ai") == "https://api.typesafe.ai/v1/systemone"
    assert JevClient._system_one_url("https://api.typesafe.ai/v1") == "https://api.typesafe.ai/v1/systemone"
    assert JevClient._system_one_url("https://api.typesafe.ai/v1/systemone") == "https://api.typesafe.ai/v1/systemone"


def test_evaluation_string_fields_are_normalized():
    evaluation = Evaluation.model_validate({
        "requirement_id": "depth",
        "value": 2,
        "confidence": 85,
        "evidence": "Built production APIs",
        "raw": "Strong evidence",
    })
    assert evaluation.evidence.quote == "Built production APIs"
    assert evaluation.evidence.status == "sufficient"
    assert evaluation.raw == {"model_output": "Strong evidence"}
    assert evaluation.confidence == .85


def test_score_match():
    result = classify(req(), Evaluation(requirement_id="depth", value=2.4,
        evidence=Evidence(quote="built services", status="sufficient")))
    assert result.verdict == "Match"
    assert result.points == 100


def test_missing_evidence_is_unscored_not_no_match():
    result = classify(req(), Evaluation(requirement_id="depth", value=None,
        evidence=Evidence(status="missing")))
    assert result.verdict == "Needs improvement — Gaps"
    assert result.points is None


def test_partial_evidence_caps_match():
    result = classify(req(), Evaluation(requirement_id="depth", value=3,
        evidence=Evidence(quote="helped build", status="partial")))
    assert result.verdict == "Needs improvement — Gaps"
    assert result.points == 50


def test_noul_is_probability_not_boolean():
    requirement = req("noul", True)
    result = classify(requirement, Evaluation(requirement_id="depth", value=.8,
        evidence=Evidence(quote="mentored engineers", status="sufficient")))
    assert result.verdict == "Match"


def test_string_encoded_score_and_noul_criteria_are_normalized():
    score = Requirement(id="years", name="Experience", jd_excerpt="4+ years", type="score",
        instructions="Rate experience",
        criteria="0: None, 1: One year, 2: Two years, 3: Three years, 4: Four years",
        target="4")
    assert score.criteria == ["None", "One year", "Two years", "Three years", "Four years"]
    assert score.target == 4
    noul = Requirement(id="mentor", name="Mentoring", jd_excerpt="mentoring", type="noul",
        instructions="Is mentoring demonstrated?",
        criteria="true: Demonstrated, false: Not demonstrated", target=None)
    assert noul.criteria == {"true": "Demonstrated", "false": "Not demonstrated"}
    assert noul.target is True


def test_score_with_more_than_ten_levels_is_safely_compacted():
    criteria = ", ".join(f"{i}: Level {i}" for i in range(11))
    requirement = Requirement(id="years", name="Experience", jd_excerpt="experience", type="score",
        instructions="Rate experience", criteria=criteria, target="10")
    assert len(requirement.criteria) == 10
    assert requirement.criteria[-1] == "Level 10"
    assert requirement.target == 9


def test_score_criteria_object_is_normalized_to_ordered_list():
    requirement = Requirement(id="years", name="Experience", jd_excerpt="5 years",
        type="score", instructions="Rate experience", criteria={"2": "Senior", "0": "None", "1": "Some"},
        target=2)
    assert requirement.criteria == ["None", "Some", "Senior"]


def test_score_target_must_be_level_index():
    with pytest.raises(ValidationError, match="level index"):
        Requirement(id="years", name="Experience", jd_excerpt="5 years", type="score",
            instructions="Rate experience", criteria=["None", "Some", "Senior"], target=5)


def test_summary_reports_coverage_separately():
    scored = classify(req(importance="required"), Evaluation(requirement_id="depth", value=2,
        evidence=Evidence(quote="built services", status="sufficient")))
    missing_req = Requirement(id="mentor", name="Mentoring", jd_excerpt="mentor", importance="preferred",
        type="noul", instructions="Mentoring?", target=True)
    missing = classify(missing_req, Evaluation(requirement_id="mentor", evidence=Evidence(status="missing")))
    summary = summarize([scored, missing])
    assert summary.fit_score == 100
    assert summary.coverage == 66.7
    assert summary.label == "Needs improvement — Gaps"
