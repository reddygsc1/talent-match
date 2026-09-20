import json
import os
import re
import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from src.clients import APIError, JevClient, OpenRouterClient
from src.models import Requirement
from src.parsers import extract_resume
from src.scoring import classify, summarize

load_dotenv()
st.set_page_config(page_title="Resume Screener", page_icon="✓", layout="wide")
st.title("Resume Screener")
st.caption("Compare one resume with one job description. Results support human review and must not be used as an automatic hiring decision.")

with st.sidebar:
    st.header("Configuration")
    openrouter_key = st.text_input("OpenRouter API key", value=os.getenv("OPENROUTER_API_KEY", ""), type="password")
    model = st.text_input("OpenRouter model", value=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"))
    jev_url = os.getenv("JEV_API_URL", "")
    jev_key = os.getenv("JEV_API_KEY", "")
    use_jev = bool(jev_url and jev_key)
    st.info("Evaluator: official JEV adapter" if use_jev else "Evaluator: OpenRouter fallback (not JEV)")
    st.caption("Keys entered here stay in this browser session and are not saved by the app.")

st.subheader("1. Add the job and resume")
left, right = st.columns(2)
with left:
    jd = st.text_area("Job description", height=280, placeholder="Paste the complete job description…")
with right:
    uploaded = st.file_uploader("Resume", type=["pdf", "docx", "txt"])
    pasted_resume = st.text_area("Or paste resume text", height=220)

if "rubric_editor" not in st.session_state:
    st.session_state.rubric_editor = ""

if st.button("Prepare requirements", type="primary"):
    if not openrouter_key or not jd.strip():
        st.error("Add an OpenRouter key and job description first.")
    else:
        try:
            with st.spinner("Preparing a job-related rubric…"):
                requirements = OpenRouterClient(openrouter_key, model).create_requirements(jd)
            st.session_state.rubric_editor = json.dumps([r.model_dump() for r in requirements], indent=2)
            st.success(f"Prepared {len(requirements)} requirements. Review them before comparison.")
        except (APIError, ValidationError) as exc:
            st.error(str(exc))

st.subheader("2. Review requirements")
st.caption("Edit or remove requirements. Required items have twice the weight of preferred items.")
rubric_text = st.text_area("Rubric (JSON)", height=340,
                           placeholder="Click Prepare requirements to generate the rubric.", key="rubric_editor")

if st.button("Compare resume"):
    try:
        if not openrouter_key:
            raise ValueError("Add your OpenRouter key.")
        if not rubric_text.strip():
            raise ValueError("Prepare or enter a rubric first.")
        requirements = [Requirement.model_validate(x) for x in json.loads(rubric_text)]
        if uploaded:
            resume = extract_resume(uploaded.name, uploaded.getvalue())
        elif pasted_resume.strip():
            resume = pasted_resume.strip()[:60000]
        else:
            raise ValueError("Upload or paste a resume.")

        ai = OpenRouterClient(openrouter_key, model)
        with st.spinner("Comparing evidence…"):
            if use_jev:
                values = JevClient(jev_url, jev_key, os.getenv("JEV_MODEL", "typesafe/jev-1.13")).evaluate(resume, requirements)
                evaluations = ai.extract_evidence(resume, requirements, values)
                evaluator = "JEV with OpenRouter evidence grounding"
            else:
                evaluations = ai.evaluate(resume, requirements)
                evaluator = "OpenRouter fallback"
            results = [classify(r, e) for r, e in zip(requirements, evaluations)]
            summary = summarize(results)
        st.session_state.results = (results, summary, evaluator)
    except (ValueError, json.JSONDecodeError, ValidationError, APIError) as exc:
        st.error(f"Could not compare: {exc}")

if "results" in st.session_state:
    results, summary, evaluator = st.session_state.results
    st.subheader("3. Results")
    a, b, c = st.columns(3)
    a.metric("Overall result", summary.label)
    b.metric("Fit score", "Not scored" if summary.fit_score is None else f"{summary.fit_score}%")
    c.metric("Evidence coverage", f"{summary.coverage}%")
    st.caption(f"Evaluator used: {evaluator}. Fit excludes missing evidence; coverage shows how much could be scored.")

    for result in results:
        icon = {"Match": "✅", "Needs improvement — Gaps": "⚠️", "No match": "❌"}[result.verdict]
        with st.expander(f"{icon} {result.requirement.name} — {result.verdict}"):
            st.write(f"**Importance:** {result.requirement.importance.title()}")
            st.write(f"**JD evidence:** “{result.requirement.jd_excerpt}”")
            value = result.evaluation.value
            st.write(f"**Evaluation:** {value if value is not None else 'Not demonstrated'}")
            if result.evaluation.evidence.quote:
                st.write(f"**Resume evidence:** “{result.evaluation.evidence.quote}”")
            st.write(f"**Gap:** {result.evaluation.gap or 'None identified'}")
            if result.evaluation.confidence is not None:
                st.write(f"**Model confidence:** {result.evaluation.confidence:.0%}")

    st.warning("Review the resume and evidence before making a decision. Model outputs can be incomplete or incorrect.")
