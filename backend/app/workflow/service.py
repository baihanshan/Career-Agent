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
                    "risk_summary": "未发现明显的证据支撑风险。",
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
            "text": "具备 Python API 开发经验",
            "importance": "high",
            "keywords": ["Python", "API"],
        }
    return {
        "requirement_id": "req_general",
        "category": "responsibility",
        "text": job_description.strip()[:120] or "通用岗位要求",
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
        "match_summary": "根据已检索到的个人材料证据，候选人与目标岗位存在可解释的匹配点。",
        "resume_bullets": [
            {
                "text": "基于个人材料中的项目证据，完成了与目标岗位相关的技术实践，并可追溯到引用证据。",
                "target_requirement_ids": [first_requirement_id],
                "evidence_ids": bullet_evidence_ids,
                "risk_level": bullet_risk,
            }
        ],
        "cover_letter": {
            "opening": "您好，我很高兴申请这个岗位。",
            "body": ["根据已引用的个人材料证据，我的项目经历与该岗位的核心要求具有较强相关性。"],
            "closing": "感谢您的时间与考虑，期待进一步交流。",
            "evidence_ids": bullet_evidence_ids,
        },
        "interview_prep": [
            {
                "topic": "基于证据的项目经历说明",
                "why_it_matters": "这个话题可以把你的个人经历和目标岗位要求直接连接起来。",
                "supporting_evidence_ids": bullet_evidence_ids,
                "prep_suggestion": "准备一段简洁的项目 walkthrough，并明确说明每个能力点对应的材料证据。",
            }
        ],
    }
