from src.models import Requirement
from src.rubric import requirements_to_rows, rows_to_requirements


def test_human_readable_rubric_round_trip():
    requirements = [
        Requirement(id="depth", name="Technical depth", jd_excerpt="deep experience",
            importance="required", type="score", instructions="Rate depth",
            criteria=["None", "Some", "Meets", "Exceeds"], target=2),
        Requirement(id="mentor", name="Mentoring", jd_excerpt="mentoring",
            importance="preferred", type="noul", instructions="Mentoring shown?",
            criteria={"true": "Has mentored", "false": "Not shown"}, target=True),
        Requirement(id="profile", name="Profile", jd_excerpt="backend",
            importance="required", type="choice", instructions="Choose profile",
            criteria={"backend": "Backend", "frontend": "Frontend"}, target="backend"),
    ]
    rows = requirements_to_rows(requirements)
    restored = rows_to_requirements(rows)
    assert [r.type for r in restored] == ["score", "noul", "choice"]
    assert restored[0].target == 2
    assert restored[0].criteria == ["None", "Some", "Meets", "Exceeds"]
    assert restored[1].target is True
    assert restored[2].target == "backend"


def test_plain_language_edits_update_rubric():
    row = requirements_to_rows([Requirement(
        id="depth", name="Depth", jd_excerpt="depth", type="score",
        instructions="Rate depth", criteria=["None", "Basic", "Strong"], target=2,
    )])[0]
    row["Criteria (one per line)"] = "0 — None\n1 — Basic\n2 — Strong\n3 — Exceptional"
    row["Expected"] = "3 — Exceptional"
    requirement = rows_to_requirements([row])[0]
    assert requirement.criteria[-1] == "Exceptional"
    assert requirement.target == 3
