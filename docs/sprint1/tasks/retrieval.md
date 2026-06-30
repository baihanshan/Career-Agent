# Retrieval 模块任务

## 目标

实现 embedding、Chroma indexing 和 evidence retrieval，使每个 JD requirement 可以检索到带 source metadata 的用户证据。

## 依赖

- `data-models.md`
- `document-processing.md`

## 完成标准

- chunks 可以被索引。
- requirement query 可以检索 evidence。
- 检索结果包含 `chunk_id`、`source_name`、`snippet`、`score`。
- 无相关证据时不伪造 evidence。

## 最小任务清单

- [x] 创建 `backend/app/retrieval/embeddings.py`。
- [x] 创建 `backend/app/retrieval/vector_store.py`。
- [x] 创建 `backend/app/retrieval/service.py`。
- [x] 创建 `backend/tests/test_retrieval.py`。
- [x] 实现 fake embedding client，用于测试稳定向量。
- [x] 写测试：fake embedding 对同一文本返回稳定结果。
- [x] 实现 Chroma vector store wrapper 的接口占位。
- [x] 写测试：`index_profile(chunks)` 会返回 index id。
- [x] 实现 `index_profile`，写入 chunk text 和 metadata。
- [x] 写测试：索引后的 metadata 包含 `chunk_id`、`source_name`、`section_label`。
- [x] 写测试：`retrieve_evidence(requirements, top_k)` 返回 `EvidenceItem[]`。
- [x] 实现 requirement query 构造逻辑，使用 requirement text 和 keywords。
- [x] 实现 evidence retrieval，把 Chroma result 转为 `EvidenceItem`。
- [x] 写测试：无匹配结果时返回空列表。
- [x] 写测试：top_k 控制每个 requirement 的最多 evidence 数。
- [x] 运行 retrieval 单元测试。
