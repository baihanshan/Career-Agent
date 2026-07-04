# CareerPilot Agent

CareerPilot Agent is an evidence-grounded, agentic job application assistant for Chinese-speaking job seekers. It turns user-provided career materials and a target job description into structured job requirements, match analysis, resume bullets, interview preparation, and role-aware risk warnings.

The project is built as a portfolio-ready LLM application: FastAPI and Pydantic provide the backend API contract, LangGraph orchestrates a fixed workflow, selected workflow stages use tool-calling ReAct agents, retrieval grounds outputs in user evidence, and a Chinese Next.js frontend exposes the end-to-end workflow.

[中文说明](README.zh.md)

## What It Does

- Accepts pasted profile materials and text-based PDF uploads.
- Parses and chunks resumes, projects, internships, skills, and education sections.
- Extracts structured JD requirements with importance, capability tags, verification mode, and interviewability.
- Retrieves evidence from the candidate's own materials using fake or BGE embeddings and in-memory or Chroma vector storage.
- Produces public, evidence-safe outputs: match summary, match analysis, three resume bullets, JD-focused interview questions, resume deep-dive questions, and top risk warnings.
- Evaluates grounding, coverage, specificity, numeric claims, repeated content, and risk consistency.
- Hides internal requirement/evidence/chunk IDs from user-facing output through a public output gate.
- Shows controlled processing warnings when recoverable stages fail, instead of exposing raw agent errors or partial unsafe output.

## Current Architecture

```text
FastAPI API
  -> LangGraph fixed workflow
      -> parse_inputs
      -> index_profile
      -> jd_analyst
      -> resume_evidence_agent
      -> match_strategist
      -> resume_bullet_agent
      -> interview_prep_agent
      -> risk_auditor_agent
      -> public_output_gate
      -> finalize_response
  -> Pydantic public response

Next.js Chinese frontend
  -> profile/JD input
  -> PDF text extraction
  -> model provider settings
  -> model list lookup
  -> results, warnings, and agent trace display
```

The top-level LangGraph stays deterministic and fixed. Local semantic decisions are delegated only where they add value:

- `ResumeEvidenceAgent` uses tool-calling ReAct to select grounded evidence.
- `InterviewPrepAgent` uses lightweight ReAct to separate JD capability questions from resume deep-dive questions.
- `RiskAuditorAgent` uses role-aware ReAct auditing to prioritize real screening risks over generic soft-skill gaps.
- JD analysis and resume bullet writing remain structured one-shot LLM calls.

ReAct agents are built with the current LangChain entrypoint:

```python
from langchain.agents import create_agent
```

OpenAI can use Pydantic `response_format`. DeepSeek and OpenAI-compatible providers use JSON-mode prompting plus local fallback parsing, because provider support for Pydantic structured output is not consistent.

## Model Providers

The frontend supports a deliberately small provider set:

- Local demo provider for deterministic tests and demos.
- OpenAI.
- DeepSeek.
- OpenAI-compatible chat-completions endpoints.

Users can type a model name manually or call `POST /models/list` from the UI to fetch available remote models. API keys are accepted per request and are not written into project files.

## API Surface

- `GET /health` returns `{ "status": "ok" }`.
- `POST /analysis` runs the full analysis workflow.
- `POST /models/list` fetches model options for OpenAI, DeepSeek, or compatible providers and returns `{ models, warning }`.
- `POST /documents/parse-pdf` extracts text from text-based PDFs up to 10 MB.

`POST /analysis` returns an `AnalysisResponse` with status, public requirements, match analysis, generated assets, evaluation report, risk report, processing warnings, and agent traces. Internal IDs stay behind the public output boundary.

## Local Development

Backend:

```bash
cd "/Users/baihanshan/Desktop/Career Agent"
conda activate carrer_agent
pip install -r requirements-dev.txt
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
```

Frontend:

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm install
npm run dev
```

The frontend talks to `http://localhost:8000` by default. To override it:

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Frontend checks:

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm run check
npm run build
```

## Retrieval Options

Tests can run with deterministic fake embeddings and an in-memory vector store:

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

For local BGE and Chroma retrieval:

```bash
export BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5
export BGE_MODEL_CACHE_DIR=/Users/baihanshan/Desktop/bge-models
export CHROMA_PATH=/Users/baihanshan/Desktop/career-agent-chroma
```

The first live retrieval run may download the BGE model into `BGE_MODEL_CACHE_DIR`.

## Demo Walkthrough

1. Start the backend:

   ```bash
   conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
   ```

2. Start the frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Open `http://localhost:3000`.
4. Paste `backend/tests/fixtures/sample_profile.md` into the personal materials field, or upload a text-based PDF.
5. Paste `backend/tests/fixtures/sample_jd.txt` into the target JD field.
6. Choose the local demo provider for deterministic output, or enter a real provider API key and model.
7. Run the analysis and inspect match results, resume bullets, interview preparation, risk warnings, processing warnings, and agent traces.

See `docs/demo-walkthrough.md` for a step-by-step version.

## Testing

Stable fixtures live in `backend/tests/fixtures/`.

- `sample_profile.md` contains a compact candidate profile with education, AI coursework, skills, and a GitHub project.
- `sample_jd.txt` contains hard skills, responsibilities, and nice-to-have requirements.
- `fake_llm_*.json` files provide deterministic LLM outputs for integration tests.

Recommended verification:

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
cd frontend
npm run check
npm run build
```

## Project Boundaries

CareerPilot Agent intentionally does not handle:

- Automatic job applications.
- Browser automation.
- Multi-user login.
- Payments.
- Social features.
- Complex resume layout or document formatting.

The focus is a high-signal, evidence-grounded AI workflow that demonstrates agent architecture, retrieval, structured outputs, quality gates, and a usable Chinese frontend.

## Portfolio Summary

Architecture notes and resume-ready project bullets are available in `docs/sprint2/resume-bullets.md`.
