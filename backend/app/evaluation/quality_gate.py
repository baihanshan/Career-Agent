from __future__ import annotations

import re
from difflib import SequenceMatcher

from backend.app.workflow.domain_models import (
    EvidenceSelection,
    InternalInterviewQuestion,
    InternalRiskReport,
    QualityIssue,
    SupportType,
)


DUPLICATE_QUESTION_SIMILARITY_THRESHOLD = 0.84
SNIPPET_COPY_RATIO_THRESHOLD = 0.55
MINIMUM_COPIED_FRAGMENT_CHARS = 24

_REQUIREMENT_RESTATEMENT_PATTERNS = (
    re.compile(r"你?如何满足(?:该|这个)?岗位.*要求"),
    re.compile(r"岗位对.+要求.*(?:如何|怎么)(?:满足|符合)"),
    re.compile(r"how (?:do|would) you (?:meet|satisfy).+requirement", re.IGNORECASE),
)
class PublicOutputQualityGate:
    def validate_evidence_allowlist(
        self,
        references_by_path: dict[str, list[str]],
        allowed_evidence_ids: set[str],
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        for field_path in sorted(references_by_path):
            for index, evidence_id in enumerate(references_by_path[field_path]):
                if evidence_id.strip() and evidence_id in allowed_evidence_ids:
                    continue
                issues.append(
                    _issue(
                        code="UNKNOWN_EVIDENCE_ID",
                        field_path=f"{field_path}.{index}",
                        message="An evidence reference is empty or outside the current allowlist.",
                        retry_instruction=(
                            "Use only evidence IDs returned by tools in the current Agent invocation."
                        ),
                    )
                )
        return _sorted_issues(issues)

    def validate_interview_questions(
        self,
        questions: list[InternalInterviewQuestion],
        source_snippets: list[str],
        *,
        field_prefix: str = "interview_questions",
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        normalized_questions: list[str] = []

        for index, item in enumerate(questions):
            question_path = f"{field_prefix}.{index}.question"
            answer_path = f"{field_prefix}.{index}.sample_answer"
            if any(
                pattern.search(item.question)
                for pattern in _REQUIREMENT_RESTATEMENT_PATTERNS
            ):
                issues.append(
                    _issue(
                        code="QUESTION_RESTATES_REQUIREMENT",
                        field_path=question_path,
                        message="The question mechanically restates a JD requirement.",
                        retry_instruction=(
                            "Rewrite it as a professional scenario, technical, system-design, "
                            "or behavioral question with an explicit assessment focus."
                        ),
                    )
                )

            for snippet in source_snippets:
                if _copies_source(item.question, snippet):
                    issues.append(
                        _issue(
                            code="QUESTION_COPIES_SNIPPET",
                            field_path=question_path,
                            message="The question copies an excessive continuous source fragment.",
                            retry_instruction=(
                                "Refer to the experience by name or a one-sentence summary, "
                                "then ask one focused professional question."
                            ),
                        )
                    )
                    break

            for snippet in source_snippets:
                if _copies_source(item.sample_answer, snippet):
                    issues.append(
                        _issue(
                            code="ANSWER_COPIES_SNIPPET",
                            field_path=answer_path,
                            message="The answer copies an excessive continuous source fragment.",
                            retry_instruction=(
                                "Reorganize supported facts into a direct, natural answer with "
                                "decisions, trade-offs, results, and reflection."
                            ),
                        )
                    )
                    break

            normalized = _normalize_question(item.question)
            if any(
                SequenceMatcher(None, normalized, previous).ratio()
                >= DUPLICATE_QUESTION_SIMILARITY_THRESHOLD
                for previous in normalized_questions
            ):
                issues.append(
                    _issue(
                        code="DUPLICATE_QUESTION",
                        field_path=question_path,
                        message="The question is semantically too similar to an earlier question.",
                        retry_instruction=(
                            "Choose a different assessment focus, such as architecture, metrics, "
                            "debugging, trade-offs, collaboration, or reflection."
                        ),
                    )
                )
            normalized_questions.append(normalized)

        return _sorted_issues(issues)

    def validate_answer_relevance(
        self,
        question: str,
        answer: str,
        *,
        field_path: str,
    ) -> list[QualityIssue]:
        normalized_answer = _normalize_for_copy(answer)
        if len(normalized_answer) >= 8:
            return []
        return [
            _issue(
                code="ANSWER_NOT_RELEVANT",
                field_path=field_path,
                message="The answer is too short to respond meaningfully to the question.",
                retry_instruction=(
                    "Answer the question directly and include supported decisions, validation, "
                    "results, or reflection where relevant."
                ),
                severity="medium",
            )
        ]

    def validate_risk_consistency(
        self,
        report: InternalRiskReport,
        evidence_selections: list[EvidenceSelection],
    ) -> list[QualityIssue]:
        selection_by_requirement = {
            item.requirement_id: item for item in evidence_selections
        }
        issues: list[QualityIssue] = []
        for index, risk in enumerate(report.risks):
            risk_type = risk.risk_type.casefold()
            title = risk.title.casefold()
            claims_missing = (
                risk_type in {"resume_coverage", "jd 未覆盖", "missing_coverage"}
                or "未覆盖" in title
                or "能力缺失" in title
                or "missing coverage" in title
            )
            if not claims_missing:
                continue
            contradicts = any(
                (selection := selection_by_requirement.get(requirement_id)) is not None
                and selection.support_level in {"strong", "partial"}
                and any(
                    support_type in selection.support_types
                    for support_type in {SupportType.DIRECT, SupportType.INDIRECT}
                )
                for requirement_id in risk.requirement_ids
            )
            if contradicts:
                issues.append(
                    _issue(
                        code="RISK_CONTRADICTS_EVIDENCE",
                        field_path=f"risks.{index}",
                        message="A missing-coverage risk contradicts sufficient resume evidence.",
                        retry_instruction=(
                            "Re-evaluate full-resume evidence strength and remove or narrow the risk."
                        ),
                    )
                )
        return _sorted_issues(issues)


def quality_issues_to_retry_message(issues: list[QualityIssue]) -> str:
    if not issues:
        return "No quality issues were found."
    lines = ["Revise only the following validation failures:"]
    lines.extend(
        f"- [{issue.code}] {issue.field_path}: {issue.retry_instruction}"
        for issue in _sorted_issues(issues)
    )
    return "\n".join(lines)


def _copies_source(output: str, snippet: str) -> bool:
    normalized_output = _normalize_for_copy(output)
    normalized_snippet = _normalize_for_copy(snippet)
    if not normalized_output or not normalized_snippet:
        return False
    match = SequenceMatcher(None, normalized_output, normalized_snippet).find_longest_match()
    ratio = match.size / len(normalized_output)
    return (
        match.size >= MINIMUM_COPIED_FRAGMENT_CHARS
        and ratio >= SNIPPET_COPY_RATIO_THRESHOLD
    )


def _normalize_for_copy(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _normalize_question(value: str) -> str:
    normalized = value.casefold()
    replacements = {
        "为什么": "原因",
        "为何": "原因",
        "选择": "选型",
        "选用": "选型",
        "主要": "关键",
        "请说明": "",
        "请介绍": "",
        "是什么": "",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return _normalize_for_copy(normalized)


def _issue(
    *,
    code: str,
    field_path: str,
    message: str,
    retry_instruction: str,
    severity: str = "high",
) -> QualityIssue:
    return QualityIssue(
        code=code,
        field_path=field_path,
        message=message,
        retry_instruction=retry_instruction,
        severity=severity,
    )


def _sorted_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    return sorted(issues, key=lambda item: (item.field_path, item.code))
