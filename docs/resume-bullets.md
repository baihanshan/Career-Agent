# CareerPilot Agent Portfolio Notes

## Resume Bullets

- Built an evidence-grounded career application agent with FastAPI, Pydantic, LangGraph, retrieval, and a Chinese Next.js frontend to generate match analysis, resume bullets, cover letter drafts, and interview preparation notes from user-provided profile materials and job descriptions.
- Implemented a deterministic multi-step AI workflow covering document chunking, fake embeddings, evidence retrieval, structured JD extraction, match scoring, evidence-grounded writing, and evaluator checks for unsupported claims, coverage gaps, and specificity risks.
- Added stable fixture-driven integration tests with sample profile/JD data and fake LLM outputs, enabling the full workflow to run without live model dependencies while preserving evidence references and risk warnings.

## Architecture Summary

CareerPilot Agent is organized as a four-layer AI application. The frontend is a Chinese Next.js single-page app for collecting profile materials and job descriptions, displaying workflow status, generated assets, evidence references, and risk warnings. The backend is a FastAPI service with Pydantic request and response schemas. The workflow layer uses LangGraph to orchestrate deterministic nodes: input parsing, document processing, profile indexing, JD analysis, evidence retrieval, match scoring, application writing, grounding evaluation, and response finalization. The retrieval and LLM layers are abstracted behind testable services; the MVP uses fake embeddings, an in-memory vector store, and deterministic fake LLM outputs so the system can be tested and demoed reliably without live provider dependencies.
