from __future__ import annotations

import re

from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.workflow.domain_models import ExperienceRecord


_YEAR_MONTH = r"\d{4}\s*年\s*\d{1,2}\s*月"
_ENGLISH_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}"
_DATE_POINT = rf"(?:{_YEAR_MONTH}|{_ENGLISH_MONTH}|\d{{4}}[./-]\d{{1,2}}|Present|至今)"
DATE_RANGE_PATTERN = re.compile(
    rf"(?P<date>{_DATE_POINT}\s*(?:-|–|—|至|到)\s*{_DATE_POINT})",
    re.IGNORECASE,
)
_PROJECT_ROLE_PATTERN = re.compile(
    r"^(?P<role>项目负责人|项目成员|Scrum Master|Project Lead|Project Manager|Team Lead)\s*(?P<name>.*)$",
    re.IGNORECASE,
)
_INTERNSHIP_HEADER_PATTERN = re.compile(
    r"^(?P<role>.+?(?:实习生|Intern))\s+(?P<company>.+)$",
    re.IGNORECASE,
)
_NON_HEADER_PREFIXES = (
    "项目介绍",
    "个人贡献",
    "项目成果",
    "职责",
    "成果",
)
_TECHNOLOGY_TERMS = (
    "DeepLabV3+",
    "PyTorch",
    "Python",
    "NLP",
    "Permutation Importance",
    "Pearson",
    "SMOTE",
    "KS/KL",
    "XGBoost",
    "LightGBM",
    "大语言模型",
    "多智能体",
    "RAG",
    "SentenceTransformers",
    "HNSWlib",
    "混淆矩阵",
    "ground truth",
)


def split_experience_text(text: str) -> list[str]:
    """Split one project/internship section without rewriting its source text."""
    lines = text.splitlines()
    header_indexes = [
        index for index, line in enumerate(lines) if _is_experience_header(line)
    ]
    if not header_indexes:
        stripped = text.strip()
        return [stripped] if stripped else []

    starts = header_indexes
    records: list[str] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        prefix_start = 0 if position == 0 else start
        segment = "\n".join(lines[prefix_start:end]).strip()
        if segment:
            records.append(segment)
    return records


def parse_experience_records(
    document: ProfileDocument,
    chunks: list[ProfileChunk],
) -> list[ExperienceRecord]:
    records: list[ExperienceRecord] = []
    counts = {"project": 0, "internship": 0}
    for chunk in chunks:
        if chunk.section_type not in counts:
            continue
        experience_type = chunk.section_type
        counts[experience_type] += 1
        ordinal = counts[experience_type]
        header = extract_experience_header(chunk.text, experience_type)
        name = header["name"] or _fallback_name(experience_type, ordinal)
        responsibilities = _extract_responsibilities(chunk.text, experience_type)
        outcomes = _extract_outcomes(chunk.text, experience_type)
        records.append(
            ExperienceRecord(
                experience_id=(
                    f"{document.document_id}:experience:{experience_type}:{ordinal}"
                ),
                experience_type=experience_type,
                name=name,
                company_name=header["company_name"],
                role_title=header["role_title"],
                date_range=header["date_range"],
                objective=_extract_labeled_value(chunk.text, "项目介绍"),
                responsibilities=responsibilities,
                technologies=_extract_technologies(chunk.text),
                challenges=_extract_challenges(chunk.text),
                actions=responsibilities,
                outcomes=outcomes,
                metrics=[item for item in outcomes if re.search(r"\d", item)],
                raw_source_chunk_ids=[chunk.chunk_id],
                raw_text=chunk.text,
            )
        )
    return records


def extract_experience_header(text: str, experience_type: str) -> dict[str, str | None]:
    header_line = next(
        (line.strip() for line in text.splitlines() if _is_experience_header(line)),
        "",
    )
    date_match = DATE_RANGE_PATTERN.search(header_line)
    date_range = date_match.group("date").strip() if date_match else None
    prefix = header_line[: date_match.start()].strip() if date_match else header_line
    result: dict[str, str | None] = {
        "name": None,
        "company_name": None,
        "role_title": None,
        "date_range": date_range,
    }

    if experience_type == "project":
        match = _PROJECT_ROLE_PATTERN.match(prefix)
        if match:
            result["role_title"] = match.group("role").strip()
            result["name"] = match.group("name").strip() or None
        elif prefix:
            result["name"] = prefix
        return result

    match = _INTERNSHIP_HEADER_PATTERN.match(prefix)
    if match:
        company = re.split(r"[，,]", match.group("company"), maxsplit=1)[0].strip()
        result["role_title"] = match.group("role").strip()
        result["company_name"] = company or None
        result["name"] = company or None
    elif prefix:
        result["name"] = prefix
    return result


def _is_experience_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(_NON_HEADER_PREFIXES):
        return False
    match = DATE_RANGE_PATTERN.search(stripped)
    if not match:
        return False
    return len(stripped[: match.start()].strip()) <= 120


def _extract_responsibilities(text: str, experience_type: str) -> list[str]:
    responsibilities: list[str] = []
    collecting_contributions = False
    for line in text.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("个人贡献"):
            collecting_contributions = True
            value = _after_label(stripped)
            if value:
                responsibilities.extend(_split_numbered_items(value))
            continue
        if stripped.startswith(("项目介绍", "项目成果")):
            collecting_contributions = False
            continue
        if experience_type == "internship" and stripped.startswith(("-", "•")):
            responsibilities.append(stripped.lstrip("-• "))
        elif collecting_contributions and re.match(r"\d+[.、]\s*", stripped):
            responsibilities.append(stripped)
    return responsibilities


def _extract_outcomes(text: str, experience_type: str) -> list[str]:
    outcomes: list[str] = []
    for line in text.splitlines()[1:]:
        stripped = line.strip().lstrip("-• ")
        if stripped.startswith("项目成果"):
            value = _after_label(stripped)
            if value:
                outcomes.append(value)
        elif experience_type == "internship" and any(
            marker in stripped
            for marker in ("形成评估报告", "支持核心模型", "量化模型", "提升")
        ):
            outcomes.append(stripped)
    return outcomes


def _extract_labeled_value(text: str, label: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return _after_label(stripped) or None
    return None


def _extract_challenges(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if "难点" in line or "重点解决" in line
    ]


def _extract_technologies(text: str) -> list[str]:
    lowered = text.casefold()
    return [term for term in _TECHNOLOGY_TERMS if term.casefold() in lowered]


def _split_numbered_items(value: str) -> list[str]:
    starts = list(re.finditer(r"(?:^|\s)(\d+[.、])\s*", value))
    if not starts:
        return [value]
    return [
        value[match.start(1) : starts[index + 1].start(1) if index + 1 < len(starts) else len(value)].strip()
        for index, match in enumerate(starts)
    ]


def _after_label(value: str) -> str:
    return re.split(r"[:：]", value, maxsplit=1)[1].strip() if re.search(r"[:：]", value) else ""


def _fallback_name(experience_type: str, ordinal: int) -> str:
    label = "项目" if experience_type == "project" else "实习"
    return f"未命名{label} {ordinal}"
