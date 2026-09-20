# JEV Resume Screener

A human-in-the-loop MVP that compares one resume with one job description and reports:

- **Match**
- **Needs improvement — Gaps**
- **No match**

It shows an overall fit score, evidence coverage, exact resume evidence, per-requirement gaps, and truthful improvement suggestions. Resumes, job descriptions, and screening history are stored locally for reuse.

## Important integration note

The app supports two explicit modes:

1. **JEV adapter:** enabled when `JEV_API_URL` and `JEV_API_KEY` are configured. It calls TypeSafe's `/v1/systemone` endpoint and defaults to `jev-latest`.
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

The OpenRouter key is read only from `.env`; it is never entered or displayed in the UI. Never commit `.env`. The model can still be changed from the sidebar.

## Workflow

1. Choose a saved resume or upload/paste a new one.
2. Choose a saved job or paste a new job description.
3. Generate and edit the human-readable rubric table.
4. Compare and save the screening.
5. Review evidence, gaps, and improvement suggestions.
6. Reopen prior results from History or manage stored data in Library.

Scanned PDFs requiring OCR are not supported in this MVP.

## Local storage

SQLite data is stored at `data/talent_match.db` by default. Set `DATABASE_PATH` to change it. The database is ignored by Git. Deleting a resume or job from Library also deletes its linked screenings. Back up the database if you need durable retention. On ephemeral cloud hosting, use a persistent volume or managed database.

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
