import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, path: str | Path = "data/talent_match.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    filename TEXT,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS screenings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    evaluator TEXT NOT NULL,
                    label TEXT NOT NULL,
                    fit_score REAL,
                    coverage REAL NOT NULL,
                    rubric_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def save_resume(self, name: str, text: str, filename: str = "") -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO resumes(name, filename, text, created_at) VALUES (?, ?, ?, ?)",
                (name.strip(), filename, text, self._now()),
            )
            return int(cursor.lastrowid)

    def save_job(self, title: str, description: str) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO jobs(title, description, created_at) VALUES (?, ?, ?)",
                (title.strip(), description, self._now()),
            )
            return int(cursor.lastrowid)

    def save_screening(self, resume_id: int, job_id: int, evaluator: str,
                       summary: Any, rubric: list[dict], results: list[dict]) -> int:
        with self._connect() as db:
            cursor = db.execute("""
                INSERT INTO screenings(
                    resume_id, job_id, evaluator, label, fit_score, coverage,
                    rubric_json, results_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (resume_id, job_id, evaluator, summary.label, summary.fit_score,
                  summary.coverage, json.dumps(rubric), json.dumps(results), self._now()))
            return int(cursor.lastrowid)

    def list_resumes(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id, name, filename, created_at FROM resumes ORDER BY id DESC"
            )]

    def get_resume(self, resume_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id, title, created_at FROM jobs ORDER BY id DESC"
            )]

    def get_job(self, job_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_screenings(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT s.id, s.label, s.fit_score, s.coverage, s.created_at,
                       r.name AS resume_name, j.title AS job_title
                FROM screenings s
                JOIN resumes r ON r.id = s.resume_id
                JOIN jobs j ON j.id = s.job_id
                ORDER BY s.id DESC
            """)
            return [dict(row) for row in rows]

    def get_screening(self, screening_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("""
                SELECT s.*, r.name AS resume_name, j.title AS job_title,
                       j.description AS job_description
                FROM screenings s
                JOIN resumes r ON r.id = s.resume_id
                JOIN jobs j ON j.id = s.job_id
                WHERE s.id = ?
            """, (screening_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["rubric"] = json.loads(result.pop("rubric_json"))
            result["results"] = json.loads(result.pop("results_json"))
            return result

    def delete_resume(self, resume_id: int):
        with self._connect() as db:
            db.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))

    def delete_job(self, job_id: int):
        with self._connect() as db:
            db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def delete_screening(self, screening_id: int):
        with self._connect() as db:
            db.execute("DELETE FROM screenings WHERE id = ?", (screening_id,))
