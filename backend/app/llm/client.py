from __future__ import annotations

from typing import Any, Mapping, Protocol

from backend.app.api.schemas import (
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    JDRequirement,
)
from backend.app.llm.prompts import (
    APPLICATION_GENERATION_PROMPT,
    GROUNDING_EVALUATION_PROMPT,
    JD_REQUIREMENTS_PROMPT,
)
from backend.app.llm.structured_outputs import parse_model, parse_model_list


class LLMClient(Protocol):
    def generate(self, prompt_key: str, prompt: str, variables: Mapping[str, Any]) -> str:
        ...


class FakeLLMClient:
    def __init__(self, responses: Mapping[str, str]) -> None:
        self.responses = dict(responses)
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt_key: str, prompt: str, variables: Mapping[str, Any]) -> str:
        self.calls.append(
            {
                "prompt_key": prompt_key,
                "prompt": prompt,
                "variables": dict(variables),
            }
        )
        return self.responses[prompt_key]


class LLMService:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def extract_jd_requirements(self, job_description: str) -> list[JDRequirement]:
        raw_output = self.client.generate(
            prompt_key="extract_jd_requirements",
            prompt=JD_REQUIREMENTS_PROMPT,
            variables={"job_description": job_description},
        )
        return parse_model_list(raw_output, JDRequirement)

    def generate_application_assets(self, context: Mapping[str, Any]) -> GeneratedAssets:
        raw_output = self.client.generate(
            prompt_key="generate_application_assets",
            prompt=APPLICATION_GENERATION_PROMPT,
            variables={"context": context},
        )
        return parse_model(raw_output, GeneratedAssets)

    def evaluate_claim_grounding(
        self,
        claims: list[str],
        evidence_items: list[EvidenceItem],
    ) -> EvaluationReport:
        raw_output = self.client.generate(
            prompt_key="evaluate_claim_grounding",
            prompt=GROUNDING_EVALUATION_PROMPT,
            variables={
                "claims": claims,
                "evidence_items": [item.model_dump() for item in evidence_items],
            },
        )
        return parse_model(raw_output, EvaluationReport)
