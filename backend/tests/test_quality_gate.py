from backend.app.core.errors import ReActErrorCode
from backend.app.evaluation.quality_gate import (
    PublicOutputQualityGate,
    quality_issues_to_retry_message,
)
from backend.app.workflow.domain_models import (
    EvidenceSelection,
    InterviewAnswerPlan,
    InternalInterviewQuestion,
    InternalRiskItem,
    InternalRiskReport,
)


def test_unknown_blank_and_cross_analysis_evidence_ids_are_rejected():
    issues = PublicOutputQualityGate().validate_evidence_allowlist(
        {
            "resume_bullets.0.evidence_ids": [
                "ev_allowed",
                "",
                "ev_unknown",
                "analysis_other:ev_cross",
            ]
        },
        allowed_evidence_ids={"ev_allowed"},
    )

    assert [issue.code for issue in issues] == [
        "UNKNOWN_EVIDENCE_ID",
        "UNKNOWN_EVIDENCE_ID",
        "UNKNOWN_EVIDENCE_ID",
    ]
    assert [issue.field_path for issue in issues] == [
        "resume_bullets.0.evidence_ids.1",
        "resume_bullets.0.evidence_ids.2",
        "resume_bullets.0.evidence_ids.3",
    ]


def test_low_value_requirement_restatement_is_rejected():
    question = _question(
        "你如何满足岗位对具备扎实的 Python 编程基础和算法能力的要求？",
        "我会结合项目说明自己的能力。",
    )

    issues = PublicOutputQualityGate().validate_interview_questions([question], [])

    assert [issue.code for issue in issues] == ["QUESTION_RESTATES_REQUIREMENT"]
    assert issues[0].field_path == "interview_questions.0.question"


def test_semantically_duplicate_questions_are_rejected():
    questions = [
        _question(
            "在语义分割项目中，你为什么选择 DeepLabV3+，主要权衡是什么？",
            "我比较了边界质量和计算成本。",
        ),
        _question(
            "语义分割项目为何选用 DeepLabV3+？请说明关键权衡。",
            "我会说明精度、速度与部署成本。",
        ),
    ]

    issues = PublicOutputQualityGate().validate_interview_questions(questions, [])

    duplicate = [issue for issue in issues if issue.code == "DUPLICATE_QUESTION"]
    assert len(duplicate) == 1
    assert duplicate[0].field_path == "interview_questions.1.question"


def test_question_and_answer_that_copy_long_snippet_are_rejected():
    copied = (
        "主导搭建端到端语义分割实验平台，完成 DeepLabV3+ 的本地部署，"
        "并设计轻量级通道注意力模块实现多尺度特征融合"
    )
    question = _question(
        f"请介绍这段经历：{copied}",
        f"我的主要工作是{copied}，最终完成了实验。",
    )

    issues = PublicOutputQualityGate().validate_interview_questions(
        [question],
        [copied],
    )

    assert {issue.code for issue in issues} >= {
        "QUESTION_COPIES_SNIPPET",
        "ANSWER_COPIES_SNIPPET",
    }


def test_missing_risk_contradicting_direct_strong_evidence_is_rejected():
    selection = EvidenceSelection(
        requirement_id="req_multimodal",
        selected_evidence_ids=["ev_tencent"],
        support_level="strong",
        support_types=["direct"],
        rationale="Tencent multimodal internship directly supports this requirement.",
    )
    report = InternalRiskReport(
        risks=[
            InternalRiskItem(
                risk_type="JD 未覆盖",
                title="缺少多模态经验",
                jd_requirement_summary="掌握多模态领域经验",
                resume_current_state="未找到相关经历",
                risk_reason="简历缺少多模态项目或实习。",
                recommendation="补充多模态经历。",
                severity="high",
                requirement_ids=["req_multimodal"],
                internal_supporting_evidence_ids=[],
            )
        ]
    )

    issues = PublicOutputQualityGate().validate_risk_consistency(
        report,
        [selection],
    )

    assert [issue.code for issue in issues] == ["RISK_CONTRADICTS_EVIDENCE"]
    assert issues[0].field_path == "risks.0"


def test_retry_message_contains_only_actionable_issue_metadata():
    issues = PublicOutputQualityGate().validate_evidence_allowlist(
        {"questions.0.evidence_ids": ["ev_secret"]},
        allowed_evidence_ids=set(),
    )

    message = quality_issues_to_retry_message(issues)

    assert "UNKNOWN_EVIDENCE_ID" in message
    assert "questions.0.evidence_ids.0" in message
    assert "Use only evidence IDs returned" in message
    assert "ev_secret" not in message
    assert "reasoning" not in message.lower()


def test_quality_gate_error_codes_are_controlled():
    assert ReActErrorCode.REACT_QUALITY_GATE_FAILED == "REACT_QUALITY_GATE_FAILED"
    assert ReActErrorCode.REACT_EVIDENCE_VIOLATION == "REACT_EVIDENCE_VIOLATION"


def _question(question: str, answer: str) -> InternalInterviewQuestion:
    return InternalInterviewQuestion(
        question=question,
        question_type="technical",
        competencies_tested=["engineering judgment"],
        target_requirement_ids=["req_1"],
        answer_plan=InterviewAnswerPlan(
            direct_answer="Define the reliability target first.",
            selected_facts=["Built an API."],
            reasoning_or_tradeoffs="Balance latency, durability, and complexity.",
            result="Validate with failure injection.",
            reflection_or_transfer="Adjust the design using observed failure modes.",
        ),
        sample_answer=answer,
        supporting_evidence_ids=["ev_1"],
    )
