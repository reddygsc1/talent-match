# JEV Resume Screener

A human-in-the-loop MVP that compares one resume with one job description and reports:

- **Match**
- **Needs improvement — Gaps**
- **No match**

It shows an overall fit score, evidence coverage, exact resume evidence, and per-requirement gaps.

## Important integration note

The JEV community documentation names `typesafe/jev-1.13`, but that model was not listed in OpenRouter's catalog when this repository was created. The app therefore supports two explicit modes:

1. **JEV adapter:** enabled when `JEV_API_URL` and `JEV_API_KEY` are configured.
2. **OpenRouter fallback:** allows local MVP testing and is clearly labeled **not JEV** in the UI.

OpenRouter is also used to extract the JD rubric and ground decisions in exact resume evidence.

## Run locally

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your key to `.env`:

```dotenv
OPENROUTER_API_KEY=your_key_here
```

Then run:

```bash
streamlit run app.py
```

Open <http://localhost:8501>.

You can also enter the OpenRouter key in the sidebar for the current session. Never commit `.env`.

## Workflow

1. Paste a job description.
2. Upload one PDF, DOCX, or TXT resume (or paste resume text).
3. Generate and review the editable JSON rubric.
4. Compare the resume.
5. Review every result and its supporting evidence.

Scanned PDFs requiring OCR are not supported in this MVP.

## Scoring

- Required requirements have weight 2; preferred requirements have weight 1.
- Match = 100, partial match = 50, demonstrated no match = 0.
- Missing evidence is unscored, not treated as failure.
- Fit score and evidence coverage are always shown separately.
- A required requirement that is not a match prevents the overall `Match` label.

JEV `score` values are zero-based rubric levels. JEV `noul` values are probabilities of yes—not booleans and not fit percentages.

## Tests

```bash
pytest -q
```

## Privacy and fair-use limits

Resume contents are sent to configured model providers. The MVP does not intentionally persist documents. It excludes protected personal traits from scoring prompts, but model results can still be wrong or biased. This tool must support human review and must not automatically reject candidates or make final employment decisions.
