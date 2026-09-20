# Product Specification

## Goal

Compare one resume against one job description using an editable, job-related rubric and return Match, Needs improvement — Gaps, or No match for each requirement.

## MVP

- One JD and one resume per run
- PDF, DOCX, TXT, and pasted text input
- AI-generated, user-editable rubric
- Score, Noul, and Choice question support
- Configurable JEV HTTP adapter
- OpenRouter fallback, visibly labeled as not JEV
- Exact evidence quotes, gaps, fit score, and evidence coverage
- In-memory session state only

## Evaluation semantics

- Score: ordered zero-based levels; fractional outputs are permitted.
- Noul: probability of yes from 0 to 1; it is not an automatic boolean.
- Choice: one key from an unordered option map.
- Missing evidence is unknown and remains unscored.

## Overall result

Required attributes weigh 2 and preferred attributes weigh 1. Match scores 100, a demonstrated partial match scores 50, and demonstrated failure scores 0. Overall Match requires fit >=80%, coverage >=80%, and all required attributes matching. No match requires fit <50% with coverage >=80%. Other outcomes are Needs improvement — Gaps.

## Non-functional requirements

- Secrets never committed or logged
- Uploaded files not intentionally persisted
- Exact evidence quotes verified against extracted resume text
- API errors shown to users rather than replaced with fake output
- Protected traits excluded from model instructions and scoring
- Human review required for every employment decision
