from __future__ import annotations

import json
import os
from typing import Any, Mapping
from uuid import uuid4

from backend.app.api.schemas import AnalysisRequest, RunConfig
from backend.app.llm.client import (
    LLMService,
    OpenAICompatibleChatClient,
    OpenAIResponsesClient,
)
from backend.app.retrieval.embeddings import BGEEmbeddingClient, FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import ChromaVectorStore, InMemoryVectorStore
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices


def run_analysis(request: AnalysisRequest) -> dict:
    response = run_workflow(request=request, services=_default_services(request.run_config))
    return response.model_dump(mode="json")


def _default_services(run_config: RunConfig) -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=_default_retrieval_service(),
        llm_service=LLMService(client=_default_llm_client(run_config)),
    )


def _default_retrieval_service() -> RetrievalService:
    if os.getenv("RETRIEVAL_BACKEND", "").strip().lower() == "fake":
        return _fake_retrieval_service()

    try:
        return RetrievalService(
            embedding_client=BGEEmbeddingClient(),
            vector_store=ChromaVectorStore(
                collection_name=f"analysis_{uuid4().hex}",
                persist_path=os.getenv(
                    "CHROMA_PATH",
                    "/Users/baihanshan/Desktop/career-agent-chroma",
                ),
            ),
        )
    except RuntimeError:
        return _fake_retrieval_service()


def _fake_retrieval_service() -> RetrievalService:
    return RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )


def _default_llm_client(run_config: RunConfig):
    if run_config.provider == "openai" and run_config.api_key:
        model = run_config.model if run_config.model != "default" else "gpt-4.1"
        return OpenAIResponsesClient(
            api_key=run_config.api_key,
            model=model,
            temperature=run_config.temperature,
        )

    if run_config.provider == "deepseek" and run_config.api_key:
        model = run_config.model if run_config.model != "default" else "deepseek-v4-flash"
        return OpenAICompatibleChatClient(
            api_key=run_config.api_key,
            model=model,
            base_url=run_config.base_url or "https://api.deepseek.com",
            temperature=run_config.temperature,
            force_json_object=True,
        )

    if run_config.provider == "openai_compatible" and run_config.api_key:
        model = run_config.model if run_config.model != "default" else "default"
        return OpenAICompatibleChatClient(
            api_key=run_config.api_key,
            model=model,
            base_url=run_config.base_url or "https://api.openai.com/v1",
            temperature=run_config.temperature,
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _DeterministicWorkflowLLMClient()

    requested_model = run_config.model if run_config.model != "default" else ""
    model = requested_model or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4.1"
    return OpenAIResponsesClient(
        api_key=api_key,
        model=model,
        temperature=run_config.temperature,
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
