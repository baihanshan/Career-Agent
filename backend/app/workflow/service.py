from __future__ import annotations

import json
from typing import Any, Mapping

from backend.app.api.schemas import AnalysisRequest
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices


def run_analysis(request: AnalysisRequest) -> dict:
    response = run_workflow(request=request, services=_default_services())
    return response.model_dump(mode="json")


def _default_services() -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=RetrievalService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=InMemoryVectorStore(),
        ),
        llm_service=LLMService(client=_DeterministicWorkflowLLMClient()),
    )


class _DeterministicWorkflowLLMClient:
    def generate(self, prompt_key: str, prompt: str, variables: Mapping[str, Any]) -> str:
        if prompt_key == "extract_jd_requirements":
            return json.dumps([_requirement_from_jd(variables["job_description"])])
        if prompt_key == "generate_application_assets":
            return json.dumps(_assets_from_context(variables["context"]))
        if prompt_key == "evaluate_claim_grounding":
            return json.dumps(
                {
                    "grounding_warnings": [],
                    "coverage_gaps": [],
                    "specificity_notes": [],
                    "risk_summary": "No major grounding risks found.",
                    "overall_status": "pass",
                }
            )
        raise KeyError(prompt_key)


def _requirement_from_jd(job_description: str) -> dict[str, Any]:
    lowered = job_description.lower()
    if "python" in lowered or "api" in lowered:
        return {
            "requirement_id": "req_python_api",
            "category": "hard_skill",
            "text": "Python API experience",
            "importance": "high",
            "keywords": ["Python", "API"],
        }
    return {
        "requirement_id": "req_general",
        "category": "responsibility",
        "text": job_description.strip()[:120] or "General role requirement",
        "importance": "medium",
        "keywords": [],
    }


def _assets_from_context(context: Mapping[str, Any]) -> dict[str, Any]:
    requirements = context["requirements"]
    evidence_ids = context["evidence_ids"]
    first_requirement_id = requirements[0]["requirement_id"] if requirements else "req_general"
    first_evidence_id = evidence_ids[0] if evidence_ids else None
    bullet_risk = "low" if first_evidence_id else "high"
    bullet_evidence_ids = [first_evidence_id] if first_evidence_id else []

    return {
        "match_summary": "Generated summary based on retrieved profile evidence.",
        "resume_bullets": [
            {
                "text": "Built relevant project work supported by cited profile evidence.",
                "target_requirement_ids": [first_requirement_id],
                "evidence_ids": bullet_evidence_ids,
                "risk_level": bullet_risk,
            }
        ],
        "cover_letter": {
            "opening": "I am excited to apply for this role.",
            "body": ["My background aligns with the role based on the cited evidence."],
            "closing": "Thank you for your consideration.",
            "evidence_ids": bullet_evidence_ids,
        },
        "interview_prep": [
            {
                "topic": "Evidence-backed project discussion",
                "why_it_matters": "This connects your background to the target role.",
                "supporting_evidence_ids": bullet_evidence_ids,
                "prep_suggestion": "Prepare a concise walkthrough grounded in the cited evidence.",
            }
        ],
    }
