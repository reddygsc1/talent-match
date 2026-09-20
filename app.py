import hashlib
import logging
import os

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from src.clients import APIError, JevClient, OpenRouterClient
from src.models import Result, Summary
from src.parsers import extract_resume
from src.pipeline import RubricError, build_results
from src.rubric import requirements_to_rows, rows_to_requirements
from src.storage import Storage

load_dotenv()
st.set_page_config(page_title="Talent Match", page_icon="✨", layout="wide")
st.markdown("""
<style>
.stApp {background: linear-gradient(135deg, #f8fbff 0%, #f4f0ff 50%, #fff8f3 100%);}
.hero {padding: 1.5rem 1.8rem; border-radius: 22px; color: white; margin-bottom: 1.2rem;
  background: linear-gradient(120deg, #2563eb, #7c3aed 55%, #db2777);
  box-shadow: 0 16px 38px rgba(79,70,229,.22);}
.hero h1 {margin: 0; font-size: 2.35rem;} .hero p {margin: .45rem 0 0; opacity: .92;}
[data-testid="stMetric"] {background: rgba(255,255,255,.85); border: 1px solid rgba(99,102,241,.15);
  padding: 1rem; border-radius: 16px; box-shadow: 0 8px 22px rgba(30,41,59,.06);}
.powered {text-align:center; color:#64748b; padding:2rem 0 .5rem; font-size:.9rem;}
</style>
<div class="hero"><h1>✨ Talent Match</h1><p>Evidence-based resume matching with reusable profiles and actionable gap guidance.</p></div>
""", unsafe_allow_html=True)

storage = Storage(os.getenv("DATABASE_PATH", "data/talent_match.db"))
openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
jev_url = os.getenv("JEV_API_URL", "").strip()
jev_key = os.getenv("JEV_API_KEY", "").strip()

with st.sidebar:
    st.header("Talent Match")
    page = st.radio("Navigate", ["New screening", "History", "Library"], label_visibility="collapsed")
    st.divider()
    model = st.text_input("OpenRouter model", value=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"))
    st.caption("Documents are stored locally. Delete them from Library when no longer needed.")


def render_results(results: list[Result], summary: Summary, evaluator: str, saved_id: int | None = None):
    st.subheader("Results")
    a, b, c = st.columns(3)
    a.metric("Overall result", summary.label)
    b.metric("Fit score", "Not scored" if summary.fit_score is None else f"{summary.fit_score}%")
    c.metric("Evidence coverage", f"{summary.coverage}%")
    if saved_id:
        st.success(f"Saved as screening #{saved_id}. You can reopen it from History.")
    st.caption(f"Fit excludes missing evidence. Coverage shows how much of the rubric could be evaluated. Evaluation path: {evaluator}.")
    for result in results:
        icon = {"Match": "✅", "Needs improvement — Gaps": "⚠️", "No match": "❌"}[result.verdict]
        with st.expander(f"{icon} {result.requirement.name} — {result.verdict}"):
            left, right = st.columns([1, 2])
            with left:
                st.write(f"**Importance:** {result.requirement.importance.title()}")
                st.write(f"**JEV value:** {result.evaluation.value if result.evaluation.value is not None else 'Not demonstrated'}")
                if result.evaluation.confidence is not None:
                    st.write(f"**Confidence:** {result.evaluation.confidence:.0%}")
            with right:
                source_note = "verified quote" if result.requirement.source_verified else "model-derived — verify"
                st.write(f"**JD requirement ({source_note}):** “{result.requirement.jd_excerpt}”")
                if result.evaluation.evidence.quote:
                    st.write(f"**Resume evidence:** “{result.evaluation.evidence.quote}”")
                st.write(f"**Gap:** {result.evaluation.gap or 'None identified'}")
                if result.suggestion and result.verdict != "Match":
                    st.info(f"💡 **Suggested improvement:** {result.suggestion}")
    st.warning("Use this as decision support only. Review the original resume and evidence before making an employment decision.")


def selected_record(records: list[dict], label_key: str, widget_key: str):
    if not records:
        return None
    options = {f"{record[label_key]}  ·  #{record['id']}": record for record in records}
    label = st.selectbox("Choose saved item", list(options), key=widget_key)
    return options[label]


if page == "New screening":
    if not openrouter_key:
        st.error("OPENROUTER_API_KEY is not configured in .env. Add it and restart the app.")

    st.subheader("1. Choose a resume and job description")
    resume_col, job_col = st.columns(2)
    with resume_col:
        st.markdown("#### Candidate resume")
        saved_resumes = storage.list_resumes()
        resume_options = ["Saved resume", "New resume"] if saved_resumes else ["New resume"]
        resume_mode = st.radio("Resume source", resume_options, horizontal=True)
        resume_id = None
        resume_text = ""
        resume_name = ""
        resume_filename = ""
        if resume_mode == "Saved resume" and saved_resumes:
            selected = selected_record(saved_resumes, "name", "resume_choice")
            resume = storage.get_resume(selected["id"])
            resume_id, resume_text, resume_name = resume["id"], resume["text"], resume["name"]
            st.caption(f"Saved {resume['created_at']}")
        else:
            resume_name = st.text_input("Candidate/profile name", placeholder="e.g. Senior backend profile")
            uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
            pasted_resume = st.text_area("Or paste resume text", height=180)
            if uploaded:
                resume_filename = uploaded.name
                try:
                    resume_text = extract_resume(uploaded.name, uploaded.getvalue())
                except ValueError as exc:
                    st.error(str(exc))
            elif pasted_resume.strip():
                resume_text = pasted_resume.strip()[:60000]

    with job_col:
        st.markdown("#### Job description")
        saved_jobs = storage.list_jobs()
        job_options = ["New job", "Saved job"] if saved_jobs else ["New job"]
        job_mode = st.radio("Job source", job_options, horizontal=True)
        job_id = None
        job_title = ""
        jd = ""
        if job_mode == "Saved job" and saved_jobs:
            selected = selected_record(saved_jobs, "title", "job_choice")
            job = storage.get_job(selected["id"])
            job_id, job_title, jd = job["id"], job["title"], job["description"]
            st.text_area("Saved job description", value=jd, height=220, disabled=True)
        else:
            job_title = st.text_input("Job title", placeholder="e.g. Senior Backend Engineer")
            jd = st.text_area("Job description", height=220, placeholder="Paste the complete job description…")

    if "rubric_rows" not in st.session_state:
        st.session_state.rubric_rows = []
        st.session_state.rubric_version = 0

    if st.button("✨ Prepare requirements", type="primary"):
        if not openrouter_key or not jd.strip():
            st.error("Add the job description and configure OPENROUTER_API_KEY first.")
        else:
            try:
                with st.spinner("Turning the job description into an editable rubric…"):
                    requirements = OpenRouterClient(openrouter_key, model).create_requirements(jd)
                st.session_state.rubric_rows = requirements_to_rows(requirements)
                st.session_state.rubric_version += 1
                repaired = sum(requirement.rubric_repaired for requirement in requirements)
                st.success(f"Prepared {len(requirements)} requirements.")
                if repaired:
                    st.warning(f"Automatically repaired {repaired} rubric item(s). Please review them.")
            except (APIError, ValidationError) as exc:
                st.error(str(exc))

    st.subheader("2. Review the rubric")
    st.caption("Edit the plain-language table directly. For criteria, keep one level or choice per line. Changes are converted back into the JEV rubric automatically.")
    edited_rows = []
    if st.session_state.rubric_rows:
        edited = st.data_editor(
            st.session_state.rubric_rows,
            key=f"rubric_table_{st.session_state.rubric_version}",
            num_rows="dynamic", use_container_width=True, height=430,
            column_config={
                "ID": st.column_config.TextColumn(disabled=True),
                "Importance": st.column_config.SelectboxColumn(options=["Required", "Preferred"]),
                "Type": st.column_config.SelectboxColumn(options=["Score", "Noul", "Choice"]),
                "Source verified": st.column_config.CheckboxColumn(disabled=True),
                "Auto-repaired": st.column_config.CheckboxColumn(disabled=True),
                "Criteria (one per line)": st.column_config.TextColumn(width="large"),
                "Evaluation question": st.column_config.TextColumn(width="large"),
            },
        )
        edited_rows = edited.to_dict("records") if hasattr(edited, "to_dict") else edited

    if st.button("Compare and save", disabled=not bool(edited_rows)):
        st.session_state.pop("current_results", None)
        try:
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY is not configured.")
            if not resume_text:
                raise ValueError("Choose, upload, or paste a resume.")
            if not resume_name.strip():
                raise ValueError("Enter a candidate/profile name.")
            if not jd.strip() or not job_title.strip():
                raise ValueError("Enter a job title and description.")
            requirements = rows_to_requirements(edited_rows)
            ai = OpenRouterClient(openrouter_key, model)
            with st.spinner("Running JEV evaluation and grounding evidence…"):
                if jev_url and jev_key:
                    values = JevClient(jev_url, jev_key, os.getenv("JEV_MODEL", "jev-latest")).evaluate(resume_text, requirements)
                    evaluations = ai.extract_evidence(resume_text, requirements, values)
                    evaluator = "JEV + OpenRouter evidence grounding"
                else:
                    evaluations = ai.evaluate(resume_text, requirements)
                    evaluator = "OpenRouter fallback"
                results, summary = build_results(requirements, evaluations)
                try:
                    suggestions = ai.suggest_improvements(resume_text, results)
                    for result in results:
                        result.suggestion = suggestions.get(result.requirement.id, "")
                except APIError as exc:
                    logging.warning("Improvement suggestions unavailable: %s", exc)
                    st.warning("The match completed, but improvement suggestions were unavailable.")

            digest = hashlib.sha256(resume_text.encode()).hexdigest()
            if resume_id is None:
                cached = st.session_state.get("draft_resume")
                if cached and cached[0] == digest:
                    resume_id = cached[1]
                else:
                    resume_id = storage.save_resume(resume_name, resume_text, resume_filename)
                    st.session_state.draft_resume = (digest, resume_id)
            job_digest = hashlib.sha256(jd.encode()).hexdigest()
            if job_id is None:
                cached = st.session_state.get("draft_job")
                if cached and cached[0] == job_digest:
                    job_id = cached[1]
                else:
                    job_id = storage.save_job(job_title, jd)
                    st.session_state.draft_job = (job_digest, job_id)
            screening_id = storage.save_screening(
                resume_id, job_id, evaluator, summary,
                [requirement.model_dump() for requirement in requirements],
                [result.model_dump() for result in results],
            )
            st.session_state.current_results = (results, summary, evaluator, screening_id)
        except (ValueError, RubricError, ValidationError, APIError) as exc:
            st.error(f"Could not compare: {exc}")
        except Exception:
            logging.exception("Unexpected comparison failure")
            st.error("An unexpected response prevented comparison. No screening result was saved.")

    if "current_results" in st.session_state:
        render_results(*st.session_state.current_results)

elif page == "History":
    st.subheader("Screening history")
    screenings = storage.list_screenings()
    if not screenings:
        st.info("No saved screenings yet.")
    else:
        options = {
            f"{row['resume_name']} → {row['job_title']} · {row['label']} · {row['created_at']} · #{row['id']}": row["id"]
            for row in screenings
        }
        selected_label = st.selectbox("Open a saved screening", list(options))
        record = storage.get_screening(options[selected_label])
        results = [Result.model_validate(item) for item in record["results"]]
        summary = Summary(fit_score=record["fit_score"], coverage=record["coverage"], label=record["label"])
        st.caption(f"Candidate: {record['resume_name']} · Job: {record['job_title']} · Saved: {record['created_at']}")
        render_results(results, summary, record["evaluator"])
        if st.button("Delete this screening", type="secondary"):
            storage.delete_screening(record["id"])
            st.success("Screening deleted.")
            st.rerun()

else:
    st.subheader("Saved library")
    resume_tab, job_tab = st.tabs(["Resumes", "Job descriptions"])
    with resume_tab:
        st.markdown("#### Save a reusable resume")
        name = st.text_input("Profile name", key="library_resume_name")
        upload = st.file_uploader("Resume file", type=["pdf", "docx", "txt"], key="library_upload")
        pasted = st.text_area("Or paste resume", key="library_resume_text", height=130)
        if st.button("Save resume to library"):
            try:
                text = extract_resume(upload.name, upload.getvalue()) if upload else pasted.strip()
                if not name.strip() or not text:
                    raise ValueError("Add a profile name and resume.")
                storage.save_resume(name, text[:60000], upload.name if upload else "")
                st.success("Resume saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.divider()
        resumes = storage.list_resumes()
        if resumes:
            selected = selected_record(resumes, "name", "library_resume_choice")
            resume = storage.get_resume(selected["id"])
            st.text_area("Stored resume text", resume["text"], height=220, disabled=True)
            if st.button("Delete resume and its screenings"):
                storage.delete_resume(resume["id"])
                st.success("Resume deleted.")
                st.rerun()
        else:
            st.info("No saved resumes.")
    with job_tab:
        jobs = storage.list_jobs()
        if jobs:
            selected = selected_record(jobs, "title", "library_job_choice")
            job = storage.get_job(selected["id"])
            st.text_area("Stored job description", job["description"], height=250, disabled=True)
            if st.button("Delete job and its screenings"):
                storage.delete_job(job["id"])
                st.success("Job deleted.")
                st.rerun()
        else:
            st.info("Jobs are saved automatically when you run a screening.")

st.markdown('<div class="powered">Powered by JEV · Structured decisions with human review</div>', unsafe_allow_html=True)
