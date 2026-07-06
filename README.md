# CareerPilot Agent

**Language:** [English](README.md) | [简体中文](README.zh-CN.md)

CareerPilot Agent is a local AI assistant for job seekers. Give it your resume or career notes plus a target job description, and it helps you understand how well you match the role, which resume bullets to emphasize, what interview questions to prepare for, and where your application may look weak.

This project currently runs as a local web app. It is useful both as a job-search assistant demo and as an engineering portfolio project for evidence-grounded LLM workflows.

## What You Can Do With It

- Paste resume, project, internship, skill, and education materials.
- Upload a text-based PDF and extract its content.
- Paste a target job description.
- Generate a role match summary and requirement-by-requirement analysis.
- Get three resume bullets grounded in your own experience.
- Prepare for JD-focused questions and resume deep-dive questions.
- Review risk warnings, such as missing hard skills, weak evidence, or vague impact.
- Use local demo mode, OpenAI, DeepSeek, or an OpenAI-compatible model endpoint.

## What You Need

- A computer that can run Python and Node.js.
- Your career materials in text form, Markdown, or a text-based PDF.
- A target job description.
- Optional: an OpenAI, DeepSeek, or OpenAI-compatible API key if you want live model output.

No API key is required for local demo mode, but demo mode is deterministic and may produce similar-looking outputs for different inputs.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/baihanshan/Career-Agent.git
cd Career-Agent
```

### One-Command Local Launch Recommended

On macOS, double-click:

```text
scripts/start_app.command
```

Or run this in a terminal:

```bash
scripts/start_app.sh
```

On Windows, double-click:

```text
scripts\start_app.bat
```

Or run this in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1
```

The launcher will:

- Create the `carrer_agent` conda environment if it is missing.
- Install missing backend and frontend dependencies.
- Start the FastAPI backend and Next.js frontend.
- Open `http://127.0.0.1:3000`.
- Reuse an already healthy backend or frontend if one is running.
- Write backend logs to `.local/logs/backend.log`.
- Write frontend logs to `.local/logs/frontend.log`.

Press `Ctrl+C` in the launcher terminal to stop services started by the launcher.

To start without opening a browser:

```bash
scripts/start_app.sh --no-browser
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1 -NoBrowser
```

Useful macOS/Linux environment overrides:

```bash
CONDA_ENV=carrer_agent BACKEND_PORT=8000 FRONTEND_PORT=3000 scripts/start_app.sh
```

Useful Windows parameter overrides:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1 -CondaEnv carrer_agent -BackendPort 8000 -FrontendPort 3000
```

If a port is already in use but the expected service is not healthy, the launcher will stop and tell you which port to free or override.

### Manual Launch For Development

If you want separate backend and frontend terminals, start the backend first:

```bash
conda create -n carrer_agent python=3.11 -y
conda activate carrer_agent
pip install -r requirements-dev.txt
conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
```

Then start the frontend in another terminal:

```bash
cd Career-Agent/frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

The frontend talks to `http://localhost:8000` by default. If your backend uses another address, start the frontend with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## How To Use The App

1. Add your personal materials.
   Paste resume text, project notes, internship descriptions, or upload a text-based PDF.

2. Add the target job description.
   Use the real JD you are preparing for. Longer, more specific JDs usually produce better analysis.

3. Choose a model service.
   Use local demo mode for a stable offline walkthrough, or enter your own OpenAI, DeepSeek, or compatible API key for live output.

4. Run the analysis.
   The app will parse your materials, extract JD requirements, retrieve supporting evidence, generate resume and interview suggestions, and check risks.

5. Review the results.
   Use the match analysis to decide whether to apply, use the resume bullets as draft material, and use the interview section to prepare concrete answers.

## How To Read The Results

- **Match summary:** a quick overview of fit and gaps.
- **Requirement analysis:** which JD requirements are strong, partial, weak, or missing.
- **Resume bullets:** evidence-grounded bullet drafts you can adapt into a resume.
- **Interview preparation:** questions and sample answer directions for both JD skills and your own experience.
- **Risk warnings:** gaps or weak evidence that may hurt screening or interviews.
- **Processing warnings:** recoverable issues from the workflow. If the main result is present, these warnings usually mean one part was degraded rather than the whole run failing.

## Privacy Notes

- The app is designed for local development and demo use.
- API keys entered in the UI are sent with the analysis request but are not written into project files.
- Do not commit real API keys, resumes, or private job materials to the repository.
- If you use a live model provider, your submitted content is sent to that provider according to its own terms.

## Troubleshooting

- **The backend is not reachable:** make sure `uvicorn` is running on `http://localhost:8000`.
- **The frontend cannot analyze:** check the browser Network tab for the `/analysis` response.
- **PDF upload fails:** use a text-based, unencrypted PDF under 10 MB, or paste the text manually.
- **Model list fails:** check provider, API key, and Base URL. For compatible providers, the Base URL should usually point to the OpenAI-compatible root such as `/v1`.
- **Live model output fails:** try local demo mode first to confirm the app itself is running.

## For Developers

CareerPilot Agent is built as an evidence-grounded LLM application with a fixed workflow and local ReAct agents for high-value reasoning steps.

### Architecture

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

ReAct agents use the current LangChain entrypoint:

```python
from langchain.agents import create_agent
```

OpenAI can use Pydantic `response_format`. DeepSeek and OpenAI-compatible providers use JSON-mode prompting plus local fallback parsing because provider support for Pydantic structured output is not consistent.

### API Surface

- `GET /health` returns `{ "status": "ok" }`.
- `POST /analysis` runs the full analysis workflow.
- `POST /models/list` fetches model options for OpenAI, DeepSeek, or compatible providers and returns `{ models, warning }`.
- `POST /documents/parse-pdf` extracts text from text-based PDFs up to 10 MB.

`POST /analysis` returns an `AnalysisResponse` with status, public requirements, match analysis, generated assets, evaluation report, risk report, processing warnings, and agent traces. Internal IDs stay behind the public output boundary.

### Retrieval Options

Tests can run with deterministic fake embeddings and an in-memory vector store:

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

For local BGE and Chroma retrieval:

```bash
export BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5
export BGE_MODEL_CACHE_DIR=/path/to/bge-models
export CHROMA_PATH=/path/to/career-agent-chroma
```

The first live retrieval run may download the BGE model into `BGE_MODEL_CACHE_DIR`.

### Verification

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
cd frontend
npm run check
npm run build
```

Stable fixtures live in `backend/tests/fixtures/`.

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

## License

This project is licensed under the [MIT License](LICENSE).
