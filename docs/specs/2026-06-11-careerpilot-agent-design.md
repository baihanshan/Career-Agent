# CareerPilot Agent Design

Date: 2026-06-11

## Purpose

CareerPilot Agent is an agentic LLM application for job seekers. It helps a user turn their real background materials and a target job description into grounded application assets: a job match analysis, tailored resume bullets, a cover letter draft, and interview preparation notes.

The project is designed as a portfolio-grade implementation for agent developer and LLM application engineer roles. It should demonstrate practical ability in RAG, multi-step agent workflows, evidence-grounded generation, evaluation, backend/frontend integration, and deployment.

## MVP Scope

The first version focuses on the core application loop:

1. The user uploads personal career materials and a target job description.
2. The system indexes the personal materials into a searchable knowledge base.
3. An agent extracts structured requirements from the job description.
4. An agent retrieves relevant evidence from the user's materials.
5. An agent generates job-specific application content.
6. An evaluator checks whether the generated content is grounded in retrieved evidence.

The MVP will not include automatic job application submission, browser control, multi-user authentication, payment, social features, or advanced resume formatting. Those can be later extensions once the core agent loop is reliable.

## Target User

The target user is a graduate or early-career professional applying for technical roles. The user may have scattered materials such as a resume, project descriptions, coursework notes, and GitHub project summaries, but needs help tailoring those materials to specific job descriptions without inventing experience they do not have.

## Core User Flow

1. The user opens the web app.
2. The user uploads or pastes personal materials:
   - Resume PDF or Markdown
   - Project descriptions
   - Coursework or skill notes
   - Optional GitHub project summaries
3. The user pastes a target job description.
4. The backend parses and indexes the personal materials.
5. The job description analyzer extracts requirements.
6. The matching agent compares requirements against retrieved personal evidence.
7. The writer agent produces:
   - Match summary
   - Tailored resume bullet suggestions
   - Cover letter draft
   - Interview preparation topics
8. The evaluator agent returns grounding and coverage checks.
9. The frontend displays generated content with evidence references and warnings.

## System Architecture

The MVP has four main layers:

### Frontend

Use Next.js and React for the user interface.

Responsibilities:

- Upload or paste user materials.
- Paste target job description.
- Trigger analysis.
- Display progress states for indexing, analysis, generation, and evaluation.
- Show generated outputs with evidence citations.
- Show evaluator warnings when content is weakly grounded.

### Backend API

Use Python and FastAPI.

Responsibilities:

- Accept uploaded files and text input.
- Parse documents into text.
- Coordinate indexing and agent execution.
- Expose endpoints for creating an analysis run and retrieving results.
- Keep request and response schemas explicit with Pydantic models.

### Retrieval Layer

Use Chroma as the local vector database.

Responsibilities:

- Chunk user materials into semantically useful passages.
- Generate embeddings.
- Store chunks with metadata.
- Retrieve evidence relevant to job requirements and generation tasks.

Metadata should include source file, section label if available, chunk id, and character offsets when possible.

### Agent Workflow

Use LangGraph to define a controlled state machine rather than a loose autonomous agent.

The graph should include these nodes:

- `parse_inputs`: normalize user materials and job description.
- `index_profile`: chunk and embed user materials.
- `analyze_jd`: extract structured requirements from the job description.
- `retrieve_evidence`: retrieve relevant user evidence for each requirement.
- `score_match`: estimate match strength and skill gaps.
- `write_application`: generate resume bullets, cover letter, and interview preparation notes.
- `evaluate_grounding`: check whether generated claims are supported by retrieved evidence.
- `finalize_response`: package final output for the frontend.

The workflow is intentionally deterministic at the graph level. LLM calls are used inside specific nodes, but node order and state transitions remain explicit.

## Data Flow

Input data:

- `profile_documents`: uploaded files or pasted text
- `job_description`: pasted text
- `run_config`: model name, temperature, retrieval parameters

Intermediate state:

- `profile_chunks`
- `jd_requirements`
- `retrieved_evidence`
- `match_analysis`
- `generated_assets`
- `evaluation_report`

Output data:

- Job match summary
- Requirement-by-requirement evidence table
- Tailored resume bullets
- Cover letter draft
- Interview preparation topics
- Grounding and hallucination warnings

## LLM Responsibilities

The LLM should be used for language and reasoning tasks, not for hidden control flow.

LLM tasks:

- Extract structured job requirements.
- Summarize relevant evidence.
- Draft application materials.
- Judge whether claims are supported by evidence.

Non-LLM tasks:

- File handling
- Chunking
- Embedding storage
- Retrieval
- API validation
- Workflow control
- Persistence
- Rendering UI state

## Evidence Grounding Rules

Generated application content must follow these rules:

1. Any claim about the user's experience must be traceable to retrieved evidence.
2. If evidence is weak, the system should label the claim as weak instead of presenting it confidently.
3. The writer agent should not invent employers, project outcomes, metrics, tools, or dates.
4. The evaluator should flag unsupported claims and missing JD requirements.

The frontend should make grounding visible by showing source snippets or source labels next to important outputs.

## Evaluation

The MVP will start with a custom evaluator instead of relying only on an external evaluation library.

Evaluator checks:

- Grounding: Are generated claims supported by retrieved evidence?
- Coverage: Did the output address the most important JD requirements?
- Specificity: Are bullets concrete rather than generic?
- Risk: Does the content contain invented numbers, employers, tools, or outcomes?

Later versions can add Ragas or LangSmith evaluation, but the first version should keep evaluation understandable and inspectable.

## Error Handling

Expected errors and responses:

- Empty or unreadable file: show a clear upload error.
- Unsupported file type: reject with accepted formats.
- Very short profile input: warn that output quality will be limited.
- Very long job description: summarize or truncate with a visible warning.
- Retrieval returns weak evidence: continue generation but label weak matches.
- LLM call fails: retry once, then return a recoverable error.
- Vector store failure: return an indexing error and avoid generation.

## Testing Strategy

The first version should include focused tests around the highest-risk behavior.

Backend tests:

- Pydantic schema validation.
- Document chunking.
- Requirement extraction output shape.
- Retrieval returns chunks with metadata.
- LangGraph workflow reaches final state for a fixture input.
- Evaluator flags unsupported claims in a controlled example.

Frontend tests:

- Upload and paste forms render.
- Analysis result sections render.
- Warning states render when evaluator returns risks.

Integration tests:

- A small sample profile and sample job description produce a complete analysis response.
- Generated claims include evidence references.

## Suggested Tech Stack

- Python 3.11+
- FastAPI
- Pydantic
- LangGraph
- LangChain or LlamaIndex for retrieval utilities
- Chroma
- OpenAI API for the first implementation
- Next.js
- React
- TypeScript
- Docker

## Milestones

### Milestone 1: Backend Skeleton

- Create FastAPI app.
- Define request and response schemas.
- Add health check.
- Add sample analysis endpoint returning mocked data.

### Milestone 2: Document Ingestion and Retrieval

- Parse plain text and Markdown first.
- Add PDF parsing after text ingestion works.
- Chunk profile material.
- Store chunks in Chroma.
- Retrieve chunks for a sample query.

### Milestone 3: LangGraph Workflow

- Build the graph state.
- Add job description analysis node.
- Add retrieval node.
- Add match scoring node.
- Add writer node.
- Add evaluator node.

### Milestone 4: Frontend MVP

- Build upload and paste interface.
- Trigger backend run.
- Render match analysis, bullets, cover letter, and evaluation warnings.

### Milestone 5: Portfolio Polish

- Add sample data.
- Add README with architecture diagram and screenshots.
- Add Docker setup.
- Add deployment instructions.
- Add a short technical write-up explaining design choices.

## Resume Positioning

A concise resume bullet for this project could be:

Built CareerPilot Agent, an agentic LLM application using FastAPI, LangGraph, Chroma, and React that converts user career materials and job descriptions into grounded resume bullets, cover letters, and interview plans with evidence citations and hallucination checks.

After implementation, the bullet should be updated with measurable details such as latency, number of evaluation cases, supported file types, or deployment metrics.

## Open Decisions

These decisions should be made during implementation planning:

- Whether to use LangChain retrieval utilities or LlamaIndex as the main retrieval abstraction.
- Whether the first frontend should use plain CSS, Tailwind, or an existing component library.
- Whether to store user data only locally for the MVP or add a lightweight database.
- Which OpenAI model to use as the default for cost and quality balance.

## Success Criteria

The MVP is successful when:

- A user can provide profile materials and a job description.
- The app produces a complete job match analysis.
- The generated bullets and cover letter are grounded in retrieved evidence.
- Unsupported or risky claims are flagged.
- The architecture is clear enough to explain in an interview.
- The repository includes tests, sample data, and a README suitable for recruiters or hiring managers.
