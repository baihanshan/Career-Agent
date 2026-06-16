# Docker Strategy

The MVP currently uses a local development setup instead of Docker.

## Current Local Runtime

- Backend runs in the conda environment `carrer_agent`.
- Backend dependencies are installed from `requirements-dev.txt`.
- Frontend dependencies are installed from `frontend/package-lock.json`.
- The MVP workflow uses an in-memory vector store.
- The MVP demo path uses deterministic fake LLM responses.

## Why Docker Is Deferred

The current runtime has no required external database, queue, or model service. The project is easier to inspect and evaluate locally with:

```bash
conda run -n carrer_agent python -m pytest backend/tests
cd frontend && npm run build
```

Adding Docker before introducing real OpenAI and Chroma services would mostly wrap local commands without simplifying the demo.

## Future Docker Compose Shape

When moving beyond the MVP, add:

- `backend` service for FastAPI
- `frontend` service for Next.js
- `chroma` service or persistent vector-store volume
- environment variables sourced from `.env.example`

Suggested service ports:

- Backend: `8000`
- Frontend: `3000`
- Chroma: `8001` or the selected Chroma default
