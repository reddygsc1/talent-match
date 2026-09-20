import pytest
from pydantic import ValidationError
from src.models import Evidence, Evaluation, Requirement
from src.scoring import classify, summarize


def req(kind="score", target=2, importance="required"):
    criteria = ["none", "basic", "strong", "expert"] if kind == "score" else {"true": "yes", "false": "no"}
    return Requirement(id="depth", name="Depth", jd_excerpt="strong depth", importance=importance,
                       type=kind, instructions="Evaluate depth", criteria=criteria, target=target)


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
