from __future__ import annotations

import json
from typing import Any, Mapping, Protocol

import httpx

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
from backend.app.llm.structured_outputs import (
    parse_evaluation_report,
    parse_generated_assets,
    parse_jd_requirements,
)


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


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.http_client = http_client or httpx.Client(timeout=60)

    def generate(self, prompt_key: str, prompt: str, variables: Mapping[str, Any]) -> str:
        response = self.http_client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": prompt,
                "input": json.dumps(
                    {
                        "prompt_key": prompt_key,
                        "variables": variables,
                    },
                    ensure_ascii=False,
                ),
                "temperature": self.temperature,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return _extract_response_text(payload)


class OpenAICompatibleChatClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        temperature: float,
        force_json_object: bool = False,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.force_json_object = force_json_object
        self.http_client = http_client or httpx.Client(timeout=60)

    def generate(self, prompt_key: str, prompt: str, variables: Mapping[str, Any]) -> str:
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "prompt_key": prompt_key,
                            "variables": variables,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": self.temperature,
        }
        if self.force_json_object:
            request_body["response_format"] = {"type": "json_object"}

        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
        )
        response.raise_for_status()
        payload = response.json()
        return _extract_chat_completion_text(payload)


class LLMService:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def extract_jd_requirements(self, job_description: str) -> list[JDRequirement]:
        raw_output = self.client.generate(
            prompt_key="extract_jd_requirements",
            prompt=JD_REQUIREMENTS_PROMPT,
            variables={"job_description": job_description},
        )
        return parse_jd_requirements(raw_output)

    def generate_application_assets(self, context: Mapping[str, Any]) -> GeneratedAssets:
        raw_output = self.client.generate(
            prompt_key="generate_application_assets",
            prompt=APPLICATION_GENERATION_PROMPT,
            variables={"context": context},
        )
        return parse_generated_assets(raw_output, context)

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
        return parse_evaluation_report(raw_output)


def _extract_response_text(payload: Mapping[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = payload.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response did not include output text.")

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, Mapping):
                continue
            if content_item.get("type") == "output_text" and isinstance(
                content_item.get("text"), str
            ):
                text_parts.append(content_item["text"])

    if not text_parts:
        raise ValueError("OpenAI response did not include output text.")
    return "".join(text_parts)


def _extract_chat_completion_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Chat completion response did not include choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise ValueError("Chat completion choice was malformed.")

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Chat completion response did not include a message.")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Chat completion response did not include message content.")
    return content
