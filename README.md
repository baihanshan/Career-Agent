# CareerPilot Agent

CareerPilot Agent is an evidence-grounded job application assistant. The MVP turns user-provided career materials and a target job description into structured match analysis, resume bullets, a cover letter draft, interview preparation notes, and visible evidence or risk warnings.

## MVP Scope

- Paste or upload career materials.
- Paste a target job description.
- Parse and chunk profile materials.
- Extract structured job requirements.
- Retrieve evidence from user materials.
- Generate application assets with evidence references.
- Evaluate grounding, coverage, specificity, and hallucination risk.
- Display results, evidence, and warnings in a web UI.

## Non-MVP Scope

- Automatic job applications.
- Browser control.
- Multi-user login.
- Payments.
- Social features.
- Complex resume layout or formatting.

## Local Development

Backend package management uses `pip` with `requirements-dev.txt` for the MVP.

```bash
conda activate carrer_agent
pip install -r requirements-dev.txt
pytest
uvicorn backend.app.main:app --reload
```

Frontend development uses Next.js:

```bash
cd frontend
npm install
npm run dev
```

Before dependencies are installed, the frontend skeleton can be checked with:

```bash
cd frontend
npm run check
```

## Current API

- `GET /health` returns `{ "status": "ok" }`.
- `POST /analysis` accepts profile documents and a job description, validates the request, runs the workflow, and returns structured requirements, evidence, match analysis, generated assets, evaluation report, and warnings.

## Test Fixtures

Stable workflow fixtures live in `backend/tests/fixtures/`.

- `sample_profile.md` contains a compact candidate profile with education, AI coursework, skills, and a GitHub project.
- `sample_jd.txt` contains hard skills, responsibilities, and nice-to-have requirements.
- `fake_llm_*.json` files provide deterministic LLM outputs for integration tests.

These fixtures let the core workflow run in tests without depending on a live model provider or nondeterministic model responses.
