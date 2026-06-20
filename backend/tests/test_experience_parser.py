from pathlib import Path

import pytest

from backend.app.documents.chunker import chunk_profile_document
from backend.app.documents.experience_parser import parse_experience_records
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.nodes import WorkflowServices, index_profile
from backend.app.workflow.state import AnalysisState


@pytest.fixture
def pasted_resume_document():
    content = (
        Path(__file__).parent / "fixtures" / "experience_resume.txt"
    ).read_text(encoding="utf-8")
    return ProfileDocument(
        document_id="doc_experiences",
        source_name="resume.pdf",
        source_type="text",
        content=content,
    )


def test_three_continuous_projects_become_three_experience_records(
    pasted_resume_document,
):
    chunks = chunk_profile_document(pasted_resume_document)

    records = parse_experience_records(pasted_resume_document, chunks)
    projects = [record for record in records if record.experience_type == "project"]

    assert [record.name for record in projects] == [
        "自然环境中的语义分割",
        "客户反馈自动分类系统",
        "使用大语言模型识别并分类隐性性别歧视",
    ]
    assert len({record.experience_id for record in projects}) == 3
    assert all(record.raw_source_chunk_ids for record in projects)


def test_tencent_internship_extracts_only_source_backed_fields(
    pasted_resume_document,
):
    chunks = chunk_profile_document(pasted_resume_document)

    internship = next(
        record
        for record in parse_experience_records(pasted_resume_document, chunks)
        if record.experience_type == "internship"
    )

    assert internship.name == "腾讯混元部门多模态团队"
    assert internship.company_name == "腾讯混元部门多模态团队"
    assert internship.role_title == "人工智能实习生"
    assert internship.date_range == "2024 年 12 月-2025 年 1 月"
    assert len(internship.responsibilities) == 3
    assert "大语言模型" in internship.technologies
    assert "混淆矩阵" in internship.technologies
    assert any("形成评估报告" in outcome for outcome in internship.outcomes)
    assert "ground truth" in internship.raw_text
    assert internship.raw_source_chunk_ids


def test_unnamed_project_uses_stable_fallback_and_preserves_raw_source():
    document = ProfileDocument(
        document_id="doc_unnamed",
        source_name="resume.txt",
        source_type="text",
        content=(
            "项目经历\n"
            "2024 年 2 月 - 2024 年 6 月\n"
            "项目介绍：针对复杂环境构建图像处理实验。\n"
            "个人贡献：完成实验设计与结果分析。"
        ),
    )
    chunks = chunk_profile_document(document)

    first = parse_experience_records(document, chunks)
    second = parse_experience_records(document, chunks)

    assert first[0].name == "未命名项目 1"
    assert first[0].experience_id == second[0].experience_id
    assert first[0].raw_text == (
        "2024 年 2 月 - 2024 年 6 月\n"
        "项目介绍：针对复杂环境构建图像处理实验。\n"
        "个人贡献：完成实验设计与结果分析。"
    )
    assert first[0].raw_source_chunk_ids == [chunks[0].chunk_id]


def test_multiline_experience_is_not_split_into_multiple_records():
    document = ProfileDocument(
        document_id="doc_multiline",
        source_name="resume.txt",
        source_type="text",
        content=(
            "项目经历\n"
            "项目负责人 检索增强系统 2025 年 1 月 - 2025 年 5 月\n"
            "项目介绍：构建检索增强系统。\n"
            "个人贡献：\n"
            "1. 设计向量检索。\n"
            "2. 完成召回评估。\n"
            "项目成果：提升检索准确率。"
        ),
    )

    records = parse_experience_records(document, chunk_profile_document(document))

    assert len(records) == 1
    assert records[0].responsibilities == ["1. 设计向量检索。", "2. 完成召回评估。"]
    assert "项目成果：提升检索准确率。" in records[0].raw_text


def test_index_profile_writes_experience_records_and_indexes_individual_chunks(
    pasted_resume_document,
):
    vector_store = InMemoryVectorStore()
    services = WorkflowServices(
        retrieval_service=RetrievalService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=vector_store,
        ),
        llm_service=LLMService(client=object()),
    )
    state = AnalysisState(
        analysis_id="analysis_experience",
        profile_documents=[pasted_resume_document],
        job_description="需要多模态和 NLP 项目经验。",
    )

    indexed = index_profile(state, services)

    assert len(indexed.experience_records) == 4
    assert len([chunk for chunk in indexed.profile_chunks if chunk.section_type == "project"]) == 3
    assert [item.metadata["project_name"] for item in vector_store.items[:3]] == [
        "自然环境中的语义分割",
        "客户反馈自动分类系统",
        "使用大语言模型识别并分类隐性性别歧视",
    ]
