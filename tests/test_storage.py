from types import SimpleNamespace

from src.storage import Storage


def test_storage_round_trip_and_cascade(tmp_path):
    storage = Storage(tmp_path / "talent.db")
    resume_id = storage.save_resume("Candidate", "Built APIs", "resume.txt")
    job_id = storage.save_job("Backend Engineer", "Python required")
    summary = SimpleNamespace(label="Match", fit_score=90.0, coverage=100.0)
    screening_id = storage.save_screening(
        resume_id, job_id, "JEV", summary,
        [{"id": "python"}], [{"verdict": "Match"}],
    )
    assert storage.get_resume(resume_id)["text"] == "Built APIs"
    assert storage.get_job(job_id)["title"] == "Backend Engineer"
    screening = storage.get_screening(screening_id)
    assert screening["resume_name"] == "Candidate"
    assert screening["rubric"] == [{"id": "python"}]
    assert len(storage.list_screenings()) == 1

    storage.delete_resume(resume_id)
    assert storage.get_resume(resume_id) is None
    assert storage.get_screening(screening_id) is None


def test_delete_single_screening_preserves_library(tmp_path):
    storage = Storage(tmp_path / "talent.db")
    resume_id = storage.save_resume("Candidate", "Resume")
    job_id = storage.save_job("Engineer", "JD")
    summary = SimpleNamespace(label="No match", fit_score=20.0, coverage=100.0)
    screening_id = storage.save_screening(resume_id, job_id, "JEV", summary, [], [])
    storage.delete_screening(screening_id)
    assert storage.get_screening(screening_id) is None
    assert storage.get_resume(resume_id) is not None
    assert storage.get_job(job_id) is not None
