from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.documents.models import ProfileChunk, ProfileDocument, ProfileSectionType
from backend.app.documents.parser import normalize_text


_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n")
_METADATA_PATTERNS = {
    "company_name": re.compile(r"^(?:Company|公司|单位)[:：]\s*(.+?)\s*$", re.IGNORECASE),
    "role_title": re.compile(r"^(?:Role|Title|岗位|职位)[:：]\s*(.+?)\s*$", re.IGNORECASE),
    "technologies": re.compile(
        r"^(?:Tech Stack|Technologies|Technology|技术栈|技术)[:：]\s*(.+?)\s*$",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class _TextBlock:
    text: str
    section_label: str | None
    section_type: ProfileSectionType = "other"
    section_title: str | None = None
    company_name: str | None = None
    role_title: str | None = None
    project_name: str | None = None
    technologies: list[str] | None = None


def chunk_profile_document(document: ProfileDocument, max_chars: int = 800) -> list[ProfileChunk]:
    content = normalize_text(document.content)
    if not content:
        return []

    blocks = (
        _markdown_blocks(content)
        if document.source_type == "markdown"
        else _plain_text_blocks(content)
    )
    pieces: list[tuple[str, _TextBlock]] = []
    for block in blocks:
        for text in _split_long_text(block.text, max_chars=max_chars):
            pieces.append((text, block))

    return [
        ProfileChunk(
            chunk_id=f"{document.document_id}:chunk:{index}",
            document_id=document.document_id,
            source_name=document.source_name,
            section_label=block.section_label,
            section_type=block.section_type,
            section_title=block.section_title,
            company_name=block.company_name,
            role_title=block.role_title,
            project_name=block.project_name,
            technologies=block.technologies or [],
            text=text,
        )
        for index, (text, block) in enumerate(pieces, start=1)
    ]


def _plain_text_blocks(content: str) -> list[_TextBlock]:
    return [
        _TextBlock(text=paragraph.strip(), section_label=None)
        for paragraph in content.split("\n\n")
        if paragraph.strip()
    ]


def _markdown_blocks(content: str) -> list[_TextBlock]:
    blocks: list[_TextBlock] = []
    current_section_title: str | None = None
    section_lines: list[str] = []

    def flush_section() -> None:
        if not section_lines:
            return
        section_text = "\n".join(section_lines).strip()
        section_lines.clear()
        if not section_text:
            return

        section_type = _section_type_for_heading(current_section_title)
        metadata = _extract_metadata(
            section_type=section_type,
            section_title=current_section_title,
            text=section_text,
        )
        if section_type in {"project", "internship"}:
            blocks.append(
                _TextBlock(
                    text=section_text,
                    section_label=current_section_title,
                    section_type=section_type,
                    section_title=current_section_title,
                    **metadata,
                )
            )
            return

        for paragraph in _split_paragraphs(section_text):
            blocks.append(
                _TextBlock(
                    text=paragraph,
                    section_label=current_section_title,
                    section_type=section_type,
                    section_title=current_section_title,
                    **metadata,
                )
            )

    for line in content.split("\n"):
        heading_match = _MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            flush_section()
            current_section_title = heading_match.group(2).strip()
            continue

        section_lines.append(line.rstrip())

    flush_section()
    return blocks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero.")
    return [text[start : start + max_chars] for start in range(0, len(text), max_chars)]


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in _PARAGRAPH_SPLIT_PATTERN.split(text) if paragraph.strip()]


def _section_type_for_heading(heading: str | None) -> ProfileSectionType:
    if heading is None:
        return "other"

    compact = re.sub(r"\s+", "", heading.lower())
    words = re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()

    if "技能" in compact or "skill" in words:
        return "skill"
    if "教育" in compact or "education" in words:
        return "education"
    if "实习" in compact or "internship" in words or words in {"experience", "work experience"}:
        return "internship"
    if "项目" in compact or "project" in words:
        return "project"
    if "其他" in compact or words in {"other", "summary", "profile"}:
        return "other"
    return "other"


def _extract_metadata(
    section_type: ProfileSectionType,
    section_title: str | None,
    text: str,
) -> dict[str, str | list[str] | None]:
    metadata: dict[str, str | list[str] | None] = {
        "company_name": None,
        "role_title": None,
        "project_name": None,
        "technologies": [],
    }

    for line in text.split("\n"):
        stripped = line.strip().lstrip("-* ")
        for key, pattern in _METADATA_PATTERNS.items():
            match = pattern.match(stripped)
            if not match:
                continue
            value = _strip_terminal_punctuation(match.group(1))
            metadata[key] = _split_technologies(value) if key == "technologies" else value

    if section_type == "project":
        metadata["project_name"] = _extract_project_name(section_title, text)

    return metadata


def _extract_project_name(section_title: str | None, text: str) -> str | None:
    if section_title and _section_type_for_heading(section_title) == "project":
        title_without_suffix = re.sub(r"(项目经历|项目经验|projects?|project experience)", "", section_title, flags=re.IGNORECASE)
        title_without_suffix = _strip_terminal_punctuation(title_without_suffix.strip(" -:："))
        if title_without_suffix:
            return title_without_suffix

    first_line = next((line.strip().lstrip("-* ") for line in text.split("\n") if line.strip()), "")
    if not first_line:
        return None
    name = re.split(r"[:：]", first_line, maxsplit=1)[0].strip()
    return _strip_terminal_punctuation(name) if name and len(name) <= 80 else None


def _split_technologies(value: str) -> list[str]:
    return [
        _strip_terminal_punctuation(item.strip())
        for item in re.split(r"[,，、;/；]+", value)
        if _strip_terminal_punctuation(item.strip())
    ]


def _strip_terminal_punctuation(value: str) -> str:
    return value.strip().strip("。.;；,，")
