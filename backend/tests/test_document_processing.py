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


def test_chinese_project_heading_creates_project_section_metadata():
    document = ProfileDocument(
        document_id="doc_project",
        source_name="resume.md",
        source_type="markdown",
        content=(
            "## 项目经历\n\n"
            "CareerPilot Agent：构建基于 LangGraph 的求职分析系统。\n"
            "技术栈：FastAPI、LangGraph、Chroma。\n"
            "结果：提升简历证据检索质量。"
        ),
    )

    chunks = chunk_profile_document(document)

    assert len(chunks) == 1
    assert chunks[0].section_type == "project"
    assert chunks[0].section_title == "项目经历"
    assert chunks[0].project_name == "CareerPilot Agent"
    assert chunks[0].technologies == ["FastAPI", "LangGraph", "Chroma"]
    assert "结果：提升简历证据检索质量。" in chunks[0].text


def test_english_experience_heading_creates_internship_section_metadata():
    document = ProfileDocument(
        document_id="doc_internship",
        source_name="resume.md",
        source_type="markdown",
        content=(
            "## Experience\n\n"
            "Company: Acme AI\n"
            "Role: Machine Learning Intern\n"
            "Built an evaluation dashboard for retrieval quality.\n"
            "Tech Stack: Python, FastAPI, React"
        ),
    )

    chunks = chunk_profile_document(document)

    assert len(chunks) == 1
    assert chunks[0].section_type == "internship"
    assert chunks[0].company_name == "Acme AI"
    assert chunks[0].role_title == "Machine Learning Intern"
    assert chunks[0].technologies == ["Python", "FastAPI", "React"]


def test_skills_heading_is_not_misclassified_as_project_or_internship():
    document = ProfileDocument(
        document_id="doc_skills",
        source_name="resume.md",
        source_type="markdown",
        content="## 技能\n\nPython、FastAPI、LangGraph、Chroma。",
    )

    chunks = chunk_profile_document(document)

    assert chunks[0].section_type == "skill"
    assert chunks[0].project_name is None
    assert chunks[0].company_name is None


def test_plain_text_standalone_resume_headings_create_sections():
    document = ProfileDocument(
        document_id="doc_plain_resume",
        source_name="resume.pdf",
        source_type="text",
        content=(
            "教育经历\nUNSW 人工智能硕士\n"
            "项目经历\n语义分割项目\n"
            "实习经历\n腾讯人工智能实习生\n"
            "技能\nPython、PyTorch\n"
            "奖项\n校级奖学金"
        ),
    )

    chunks = chunk_profile_document(document)
    sections = {chunk.section_title: chunk.section_type for chunk in chunks}

    assert sections == {
        "教育经历": "education",
        "项目经历": "project",
        "实习经历": "internship",
        "技能": "skill",
        "奖项": "other",
    }


def test_markdown_source_accepts_unprefixed_resume_headings():
    document = ProfileDocument(
        document_id="doc_pasted_resume",
        source_name="profile.md",
        source_type="markdown",
        content="项目经历\n模型项目\n实习经历\n人工智能实习生",
    )

    chunks = chunk_profile_document(document)

    assert [chunk.section_type for chunk in chunks] == ["project", "internship"]


def test_plain_text_english_resume_headings_create_sections():
    document = ProfileDocument(
        document_id="doc_english_resume",
        source_name="resume.pdf",
        source_type="text",
        content="Education\nMSc AI\nProjects\nClassifier\nWork Experience\nAI Intern\nSkills\nPython",
    )

    chunks = chunk_profile_document(document)

    assert [chunk.section_type for chunk in chunks] == [
        "education",
        "project",
        "internship",
        "skill",
    ]


def test_heading_keyword_inside_body_does_not_split_section():
    document = ProfileDocument(
        document_id="doc_no_false_heading",
        source_name="resume.txt",
        source_type="text",
        content="项目经历\n完成模型训练，并参与项目经历复盘。",
    )

    chunks = chunk_profile_document(document)

    assert len(chunks) == 1
    assert chunks[0].section_type == "project"
    assert "参与项目经历复盘" in chunks[0].text
