from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.documents.parser import normalize_text


_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class _TextBlock:
    text: str
    section_label: str | None


def chunk_profile_document(document: ProfileDocument, max_chars: int = 800) -> list[ProfileChunk]:
    content = normalize_text(document.content)
    if not content:
        return []

    blocks = (
        _markdown_blocks(content)
        if document.source_type == "markdown"
        else _plain_text_blocks(content)
    )
    pieces: list[tuple[str, str | None]] = []
    for block in blocks:
        for text in _split_long_text(block.text, max_chars=max_chars):
            pieces.append((text, block.section_label))

    return [
        ProfileChunk(
            chunk_id=f"{document.document_id}:chunk:{index}",
            document_id=document.document_id,
            source_name=document.source_name,
            section_label=section_label,
            text=text,
        )
        for index, (text, section_label) in enumerate(pieces, start=1)
    ]


def _plain_text_blocks(content: str) -> list[_TextBlock]:
    return [
        _TextBlock(text=paragraph.strip(), section_label=None)
        for paragraph in content.split("\n\n")
        if paragraph.strip()
    ]


def _markdown_blocks(content: str) -> list[_TextBlock]:
    blocks: list[_TextBlock] = []
    current_section: str | None = None
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            text = "\n".join(paragraph_lines).strip()
            if text:
                blocks.append(_TextBlock(text=text, section_label=current_section))
            paragraph_lines.clear()

    for line in content.split("\n"):
        heading_match = _MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            flush_paragraph()
            current_section = heading_match.group(2).strip()
            continue

        if not line.strip():
            flush_paragraph()
            continue

        paragraph_lines.append(line.strip())

    flush_paragraph()
    return blocks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero.")
    return [text[start : start + max_chars] for start in range(0, len(text), max_chars)]
