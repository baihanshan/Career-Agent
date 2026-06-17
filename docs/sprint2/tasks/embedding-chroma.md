# Sprint 2 BGE Embedding 与 Chroma 检索任务

状态：已完成

## 目标

用本机 `BAAI/bge-large-zh-v1.5` 和 Chroma 替换 MVP 的 fake token-count embedding 与 in-memory vector store。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/retrieval/embeddings.py`
- `backend/app/retrieval/vector_store.py`
- `backend/app/retrieval/service.py`

## 完成标准

- 默认本机加载 `BAAI/bge-large-zh-v1.5`。
- 模型缓存目录为 `/Users/baihanshan/Desktop/bge-models`。
- Chroma 持久化目录为 `/Users/baihanshan/Desktop/career-agent-chroma`。
- 每次分析创建独立 collection。
- 分析完成后删除 collection。
- fake embedding 测试路径仍保留。

## 最小任务清单

- [x] 新增 `BGEEmbeddingClient`，封装 sentence-transformers。
- [x] 支持 MPS/GPU 优先，CPU fallback。
- [x] 支持从环境变量读取模型名和缓存目录。
- [x] 新增 `ChromaVectorStore`，封装 collection 创建、add、query、delete。
- [x] collection 命名使用 `analysis_<uuid>`。
- [x] `RetrievalService.index_profile` 写入 Chroma 时保存 section metadata。
- [x] `RetrievalService.retrieve_evidence` 支持 section_filter。
- [x] 检索结果保留 evidence_id、requirement_id、chunk_id、section_type、source_name、snippet、score。
- [x] 分析完成或失败时清理当前 collection。
- [x] 编写测试：BGE client 在 mock 模式下返回固定维度向量。
- [x] 编写测试：Chroma store 能 add/query/delete collection。
- [x] 编写测试：不同 analysis collection 不互相污染。
