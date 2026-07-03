import pytest
import httpx

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.llm.client import (
    FakeLLMClient,
    LLMService,
    OpenAICompatibleChatClient,
    OpenAIResponsesClient,
)
from backend.app.llm.prompts import (
    APPLICATION_GENERATION_PROMPT,
    GROUNDING_EVALUATION_PROMPT,
    JD_REQUIREMENTS_PROMPT,
)
from backend.app.llm.structured_outputs import LLMOutputParseError


@pytest.mark.parametrize(
    "client",
    [
        OpenAIResponsesClient(
            api_key="test-key",
            model="gpt-test",
            temperature=0.2,
        ),
        OpenAICompatibleChatClient(
            api_key="test-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            temperature=0.2,
        ),
    ],
)
def test_default_llm_clients_allow_slow_provider_responses(client):
    try:
        assert client.http_client.timeout.read == 180
    finally:
        client.http_client.close()


def test_fake_client_extracts_sample_jd_requirements():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [
                  {
                    "requirement_id": "req_python",
                    "category": "hard_skill",
                    "text": "Build Python APIs",
                    "importance": "high",
                    "keywords": ["Python", "API"]
                  }
                ]
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("We need someone to build Python APIs.")

    assert requirements == [
        JDRequirement(
            requirement_id="req_python",
            category="hard_skill",
            text="Build Python APIs",
            importance="high",
            keywords=["Python", "API"],
            capability_tags=["programming"],
            verification_mode="technical_question",
            interviewability=True,
            question_focus=(
                "applied technical decisions, alternatives, validation, "
                "and engineering trade-offs"
            ),
        )
    ]


def test_degree_requirement_defaults_to_non_interviewable_document_check():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [{
                  "requirement_id": "req_degree",
                  "category": "qualification",
                  "text": "计算机相关专业硕士或博士学历",
                  "importance": "high",
                  "keywords": ["计算机", "硕士", "博士"]
                }]
                """
            }
        )
    )

    requirement = service.extract_jd_requirements("计算机相关专业硕士或博士学历")[0]

    assert requirement.verification_mode == "document_check"
    assert requirement.interviewability is False
    assert requirement.question_focus is None


def test_programming_and_algorithm_requirement_gets_technical_semantics():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [{
                  "requirement_id": "req_programming",
                  "category": "hard_skill",
                  "text": "具备扎实的编程基础（Python/C++/Java），熟悉常用算法与数据结构",
                  "importance": "high",
                  "keywords": ["Python", "C++", "Java", "算法", "数据结构"]
                }]
                """
            }
        )
    )

    requirement = service.extract_jd_requirements("需要编程、算法与数据结构能力")[0]

    assert requirement.verification_mode == "technical_question"
    assert requirement.interviewability is True
    assert {"programming", "algorithms"}.issubset(requirement.capability_tags)
    assert requirement.question_focus


def test_multimodal_platform_responsibility_gets_system_design_focus():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [{
                  "requirement_id": "req_platform",
                  "category": "responsibility",
                  "text": "设计并开发多模态平台，建立模型效果评估体系",
                  "importance": "high",
                  "keywords": ["多模态", "平台", "评估"]
                }]
                """
            }
        )
    )

    requirement = service.extract_jd_requirements("设计多模态平台和评估体系")[0]

    assert requirement.verification_mode == "system_design"
    assert requirement.interviewability is True
    assert {"multimodal", "platform", "evaluation"}.issubset(
        requirement.capability_tags
    )
    assert all(
        term in requirement.question_focus.lower()
        for term in ("platform", "design", "evaluation")
    )


def test_at_least_one_domain_requirement_preserves_or_alternatives():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [{
                  "requirement_id": "req_domain",
                  "category": "hard_skill",
                  "text": "了解 NLP/多模态至少一个领域",
                  "importance": "high",
                  "keywords": ["NLP", "多模态"]
                }]
                """
            }
        )
    )

    requirement = service.extract_jd_requirements("了解 NLP/多模态至少一个领域")[0]

    assert requirement.logical_operator == "OR"
    assert requirement.alternatives == ["NLP", "多模态"]
    assert {"nlp", "multimodal"}.issubset(requirement.capability_tags)


def test_malformed_requirements_json_raises_parse_error():
    service = LLMService(
        client=FakeLLMClient(responses={"extract_jd_requirements": "{not json"})
    )

    with pytest.raises(LLMOutputParseError):
        service.extract_jd_requirements("Bad output please.")


def test_extract_jd_requirements_accepts_markdown_json_fence():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                ```json
                [
                  {
                    "requirement_id": "req_data",
                    "category": "hard_skill",
                    "text": "Analyze product data",
                    "importance": "high",
                    "keywords": ["data", "analysis"]
                  }
                ]
                ```
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("Need product data analysis.")

    assert requirements[0].requirement_id == "req_data"


def test_extract_jd_requirements_accepts_explanatory_text_around_json_fence():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                Here is the structured JSON:
                ```json
                [
                  {
                    "requirement_id": "req_sql",
                    "category": "hard_skill",
                    "text": "Write SQL queries",
                    "importance": "high",
                    "keywords": ["SQL"]
                  }
                ]
                ```
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("Need SQL analysis.")

    assert requirements[0].requirement_id == "req_sql"


def test_extract_jd_requirements_accepts_requirements_object_wrapper():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                {
                  "requirements": [
                    {
                      "requirement_id": "req_ops",
                      "category": "responsibility",
                      "text": "Coordinate cross-functional operations",
                      "importance": "medium",
                      "keywords": ["operations", "coordination"]
                    }
                  ]
                }
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("Need operations coordination.")

    assert requirements[0].requirement_id == "req_ops"


def test_extract_jd_requirements_normalizes_common_model_schema_variants():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                {
                  "requirements": [
                    {
                      "id": "python_backend",
                      "type": "technical_skill",
                      "description": "Python backend development",
                      "priority": "required",
                      "skills": ["Python", "Backend"]
                    },
                    "Strong communication with product stakeholders"
                  ]
                }
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("Need Python and communication.")

    assert requirements[0] == JDRequirement(
        requirement_id="python_backend",
        category="hard_skill",
        text="Python backend development",
        importance="high",
        keywords=["Python", "Backend"],
        capability_tags=["programming"],
        verification_mode="technical_question",
        interviewability=True,
        question_focus=(
            "applied technical decisions, alternatives, validation, "
            "and engineering trade-offs"
        ),
    )
    assert requirements[1] == JDRequirement(
        requirement_id="req_2",
        category="responsibility",
        text="Strong communication with product stakeholders",
        importance="medium",
        keywords=[],
        capability_tags=["communication"],
    )


def test_extract_jd_requirements_accepts_nested_analysis_wrapper_and_mandatory_priority():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                {
                  "jd_analysis": {
                    "requirements": [
                      {
                        "id": "req_backend",
                        "kind": "must_have",
                        "requirement_text": "Must have Python backend API experience",
                        "priority": "mandatory",
                        "keywords": "Python, API"
                      }
                    ]
                  }
                }
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("Must have Python backend API experience.")

    assert requirements == [
        JDRequirement(
            requirement_id="req_backend",
            category="hard_skill",
            text="Must have Python backend API experience",
                importance="high",
                keywords=["Python", "API"],
                capability_tags=["programming"],
                verification_mode="technical_question",
                interviewability=True,
                question_focus=(
                    "applied technical decisions, alternatives, validation, "
                    "and engineering trade-offs"
                ),
        )
    ]


def test_jd_prompt_defines_user_readable_text_and_importance_criteria():
    prompt = JD_REQUIREMENTS_PROMPT.lower()

    assert "user-readable" in prompt
    assert "high importance" in prompt
    assert "medium importance" in prompt
    assert "low importance" in prompt
    assert "internal" in prompt


def test_application_assets_json_parses_to_generated_assets():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": """
                {
                  "match_summary": "Strong fit for API work.",
                  "resume_bullets": [
                    {
                      "text": "Built Python APIs backed by project evidence.",
                      "target_requirement_ids": ["req_python"],
                      "evidence_ids": ["ev_python"],
                      "risk_level": "low"
                    }
                  ],
                  "interview_prep": [
                    {
                      "topic": "Python API project",
                      "why_it_matters": "The role asks for API development.",
                      "supporting_evidence_ids": ["ev_python"],
                      "prep_suggestion": "Prepare a concise project walkthrough."
                    }
                  ]
                }
                """
            }
        )
    )

    assets = service.generate_application_assets(
        context={
            "requirements": [_requirement()],
            "evidence": [_evidence()],
            "match_analysis": [],
        }
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert len(assets.resume_bullets) == 3
    assert "cover_letter" not in assets.model_dump()


def test_application_assets_normalizes_common_model_schema_variants():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": """
                {
                  "generated_assets": {
                    "summary": "The profile has relevant API evidence.",
                    "bullets": [
                      {
                        "bullet": "Built FastAPI services for a project.",
                        "requirement_id": "req_python",
                        "evidence_id": "ev_python"
                      }
                    ],
                    "interview_questions": [
                      "Explain the FastAPI project architecture."
                    ]
                  }
                }
                """
            }
        )
    )

    assets = service.generate_application_assets(
        context={
            "requirements": [_requirement().model_dump()],
            "evidence": [_evidence().model_dump()],
            "match_analysis": [
                {
                    "requirement_id": "req_python",
                    "match_level": "strong",
                    "rationale": "Evidence supports this requirement.",
                    "evidence_ids": ["ev_python"],
                }
            ],
            "evidence_ids": ["ev_python"],
            "missing_requirement_ids": [],
        }
    )

    assert assets.match_summary == "The profile has relevant API evidence."
    assert assets.resume_bullets[0].text == "Built FastAPI services for a project."
    assert assets.resume_bullets[0].target_requirement_ids == ["req_python"]
    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert len(assets.resume_bullets) == 3
    assert (
        assets.interview_prep.jd_questions[0].sample_answer
        == "Explain the FastAPI project architecture."
    )


def test_application_asset_normalization_does_not_infer_ids_from_text_or_fill_blank_ids():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": """
                {
                  "match_summary": "Relevant project evidence exists.",
                  "resume_bullets": [{
                    "text": "Built an API. (evidence_ids: [\\"ev_python\\"])",
                    "target_requirement_ids": ["req_python"],
                    "evidence_ids": [""],
                    "risk_level": "low"
                  }],
                  "interview_prep": {"jd_questions": [], "resume_deep_dive_questions": []}
                }
                """
            }
        )
    )

    assets = service.generate_application_assets(
        context={
            "requirements": [_requirement().model_dump()],
            "evidence": [_evidence().model_dump()],
            "match_analysis": [],
            "evidence_ids": ["ev_python"],
        }
    )

    assert assets.resume_bullets[0].evidence_ids == [""]
    assert "evidence_ids" in assets.resume_bullets[0].text


def test_grounding_evaluation_json_parses_to_evaluation_report():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "evaluate_claim_grounding": """
                {
                  "grounding_warnings": [
                    {
                      "asset_type": "resume_bullet",
                      "asset_id": "bullet_1",
                      "claim": "Scaled the service to one million users.",
                      "reason": "The evidence does not mention scale.",
                      "severity": "high"
                    }
                  ],
                  "coverage_gaps": [
                    {
                      "requirement_id": "req_python",
                      "reason": "Needs stronger production API evidence.",
                      "severity": "medium"
                    }
                  ],
                  "specificity_notes": ["Add project context."],
                  "risk_summary": "One unsupported scale claim.",
                  "overall_status": "pass_with_warnings"
                }
                """
            }
        )
    )

    report = service.evaluate_claim_grounding(
        claims=["Scaled the service to one million users."],
        evidence_items=[_evidence()],
    )

    assert report.grounding_warnings[0].severity == "high"
    assert report.coverage_gaps[0].requirement_id == "req_python"
    assert report.overall_status == "pass_with_warnings"


def test_grounding_evaluation_normalizes_common_model_schema_variants():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "evaluate_claim_grounding": """
                {
                  "warnings": [
                    {
                      "type": "resume",
                      "id": "bullet-1",
                      "text": "Production-ready API.",
                      "message": "Evidence does not mention production readiness.",
                      "level": "warning"
                    }
                  ],
                  "gaps": [
                    {
                      "id": "req_python",
                      "message": "Need stronger production evidence.",
                      "level": "warning"
                    }
                  ],
                  "notes": ["Add project context."],
                  "summary": "Review one warning.",
                  "status": "warning"
                }
                """
            }
        )
    )

    report = service.evaluate_claim_grounding(
        claims=["Production-ready API."],
        evidence_items=[_evidence()],
    )

    assert report.grounding_warnings[0].asset_type == "resume_bullet"
    assert report.grounding_warnings[0].asset_id == "bullet-1"
    assert report.grounding_warnings[0].severity == "medium"
    assert report.coverage_gaps[0].requirement_id == "req_python"
    assert report.overall_status == "pass_with_warnings"


def test_prompts_explicitly_forbid_fabricating_experience():
    prompts = "\n".join(
        [JD_REQUIREMENTS_PROMPT, APPLICATION_GENERATION_PROMPT, GROUNDING_EVALUATION_PROMPT]
    ).lower()

    assert "do not fabricate" in prompts
    assert "evidence" in prompts


def test_openai_responses_client_posts_prompt_and_variables():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output_text": "[{\"requirement_id\":\"req_python\"}]"})

    client = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-test",
        temperature=0.2,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    output = client.generate(
        prompt_key="extract_jd_requirements",
        prompt="Return JSON only.",
        variables={"job_description": "Need Python API experience."},
    )

    assert output == "[{\"requirement_id\":\"req_python\"}]"
    request = requests[0]
    assert request.url == "https://api.openai.com/v1/responses"
    assert request.headers["authorization"] == "Bearer test-key"
    payload = request.read().decode()
    assert '"model":"gpt-test"' in payload
    assert '"temperature":0.2' in payload
    assert "Return JSON only." in payload
    assert "Need Python API experience." in payload


def test_openai_compatible_chat_client_posts_to_deepseek_chat_completions():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "[{\"requirement_id\":\"req_deepseek\"}]"
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleChatClient(
        api_key="deepseek-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        temperature=0.3,
        force_json_object=True,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    output = client.generate(
        prompt_key="extract_jd_requirements",
        prompt="Return JSON only.",
        variables={"job_description": "Need data analysis experience."},
    )

    assert output == "[{\"requirement_id\":\"req_deepseek\"}]"
    request = requests[0]
    assert request.url == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == "Bearer deepseek-key"
    payload = request.read().decode()
    assert '"model":"deepseek-v4-flash"' in payload
    assert '"temperature":0.3' in payload
    assert '"response_format":{"type":"json_object"}' in payload
    assert "Return JSON only." in payload
    assert "Need data analysis experience." in payload


def _requirement() -> JDRequirement:
    return JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev_python",
        requirement_id="req_python",
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        snippet="Built Python FastAPI services.",
        score=0.91,
    )
