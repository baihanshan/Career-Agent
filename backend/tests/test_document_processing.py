import pytest

from backend.app.documents.chunker import chunk_profile_document
from backend.app.documents.models import ProfileDocument
from backend.app.documents.parser import normalize_text


def test_normalize_text_trims_whitespace_and_unifies_newlines():
    content = "  Built APIs.\r\n\r\n\r\nShipped tests.\r\n  "

    assert normalize_text(content) == "Built APIs.\n\nShipped tests."


def test_markdown_heading_becomes_following_chunk_section_label():
    document = ProfileDocument(
        document_id="doc_resume",
        source_name="resume.md",
        source_type="markdown",
        content="## Projects\n\nBuilt a career agent.\n\n## Skills\n\nPython and FastAPI.",
    )

    chunks = chunk_profile_document(document)

    assert [chunk.section_label for chunk in chunks] == ["Projects", "Skills"]
    assert chunks[0].text == "Built a career agent."
    assert chunks[1].text == "Python and FastAPI."


def test_empty_content_returns_no_chunks_when_defensively_called():
    document = ProfileDocument.model_construct(
        document_id="doc_empty",
        source_name="resume.txt",
        source_type="text",
        content="   ",
    )

    assert chunk_profile_document(document) == []


def test_long_paragraph_is_split_into_multiple_chunks():
    document = ProfileDocument(
        document_id="doc_long",
        source_name="resume.txt",
        source_type="text",
        content="A" * 120,
    )

    chunks = chunk_profile_document(document, max_chars=50)

    assert [chunk.text for chunk in chunks] == ["A" * 50, "A" * 50, "A" * 20]


def test_chunks_include_required_metadata_and_stable_ids():
    document = ProfileDocument(
        document_id="doc_meta",
        source_name="resume.txt",
        source_type="text",
        content="First paragraph.\n\nSecond paragraph.",
    )

    chunks = chunk_profile_document(document)

    assert [chunk.chunk_id for chunk in chunks] == ["doc_meta:chunk:1", "doc_meta:chunk:2"]
    assert [chunk.document_id for chunk in chunks] == ["doc_meta", "doc_meta"]
    assert [chunk.source_name for chunk in chunks] == ["resume.txt", "resume.txt"]
    assert [chunk.text for chunk in chunks] == ["First paragraph.", "Second paragraph."]


def test_chunk_output_order_is_stable():
    document = ProfileDocument(
        document_id="doc_order",
        source_name="resume.md",
        source_type="markdown",
        content="# One\n\nAlpha.\n\n# Two\n\nBeta.\n\nGamma.",
    )

    first_run = chunk_profile_document(document)
    second_run = chunk_profile_document(document)

    assert [chunk.model_dump() for chunk in first_run] == [
        chunk.model_dump() for chunk in second_run
    ]
    assert [chunk.text for chunk in first_run] == ["Alpha.", "Beta.", "Gamma."]
