# CareerPilot Agent

CareerPilot Agent is an evidence-grounded job application assistant. The MVP turns user-provided career materials and a target job description into structured match analysis, resume bullets, a cover letter draft, interview preparation notes, and visible evidence or risk warnings.

It is designed as a portfolio-ready AI application project: FastAPI and Pydantic handle the API and schemas, document processing and retrieval provide evidence, LangGraph orchestrates the workflow, and a Chinese Next.js frontend exposes the user workflow.

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
conda run -n carrer_agent python -m pytest backend/tests
conda run -n carrer_agent uvicorn backend.app.main:app --reload
```

Frontend development uses Next.js:

```bash
cd frontend
npm install
npm run dev
```

The frontend talks to the backend at `http://localhost:8000` by default. To override it:

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Frontend checks:

```bash
cd frontend
npm run check
npm run build
```

## Demo Walkthrough

Use the stable demo fixtures for a deterministic walkthrough:

1. Start the backend:

   ```bash
   conda run -n carrer_agent uvicorn backend.app.main:app --reload
   ```

2. Start the frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Open `http://localhost:3000`.
4. Paste `backend/tests/fixtures/sample_profile.md` into the personal materials field.
5. Paste `backend/tests/fixtures/sample_jd.txt` into the target JD field.
6. Run the analysis and inspect match summary, evidence references, generated assets, workflow warnings, and risk warnings.

See `docs/demo-walkthrough.md` for a step-by-step version.

## Current API

- `GET /health` returns `{ "status": "ok" }`.
- `POST /analysis` accepts profile documents and a job description, validates the request, runs the workflow, and returns structured requirements, evidence, match analysis, generated assets, evaluation report, and warnings.

## Test Fixtures

Stable workflow fixtures live in `backend/tests/fixtures/`.

- `sample_profile.md` contains a compact candidate profile with education, AI coursework, skills, and a GitHub project.
- `sample_jd.txt` contains hard skills, responsibilities, and nice-to-have requirements.
- `fake_llm_*.json` files provide deterministic LLM outputs for integration tests.

These fixtures let the core workflow run in tests without depending on a live model provider or nondeterministic model responses.

## Docker Strategy

This MVP currently uses a local development setup instead of Docker:

- Backend: conda environment `carrer_agent` plus `requirements-dev.txt`
- Frontend: local Node.js dependencies from `frontend/package-lock.json`
- Vector store: in-memory test vector store for the MVP workflow
- LLM: deterministic fake LLM client for stable local demos and tests

Docker is intentionally deferred until the project switches from fake/local services to external providers such as OpenAI and Chroma. At that point, a `docker-compose.yml` should define separate `backend`, `frontend`, and vector-store services with environment variables from `.env.example`.

## Portfolio Summary

Architecture summary and resume-ready project bullets are available in `docs/resume-bullets.md`.
