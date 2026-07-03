# Sprint 2 Project Setup 任务

状态：已完成

## 目标

为 Sprint 2 引入本地 BGE embedding、Chroma、本地模型缓存目录、LangGraph ReAct agent 所需依赖和配置开关。

## 依赖

- `docs/sprint2/improve.md`
- `pyproject.toml`
- `requirements-dev.txt`
- `.env.example`

## 完成标准

- 后端依赖中包含 `sentence-transformers`、`chromadb` 及 LangGraph ReAct 所需包。
- 默认 BGE 模型缓存目录为 `/Users/baihanshan/Desktop/bge-models`。
- 默认 Chroma 持久化目录为 `/Users/baihanshan/Desktop/career-agent-chroma`。
- 旧 fake/local 模式仍可用于测试。
- 依赖安装和测试命令写入 README 或 sprint2 文档。

## 最小任务清单

- [x] 更新 `requirements-dev.txt`，加入 `sentence-transformers`、`chromadb` 及必要依赖。
- [x] 更新 `pyproject.toml`，同步生产依赖。
- [x] 更新 `.env.example`，增加 `BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5`。
- [x] 更新 `.env.example`，增加 `BGE_MODEL_CACHE_DIR=/Users/baihanshan/Desktop/bge-models`。
- [x] 更新 `.env.example`，增加 `CHROMA_PATH=/Users/baihanshan/Desktop/career-agent-chroma`。
- [x] 保留 fake embedding / in-memory vector store 的测试路径。
- [x] 在 README 或 `docs/sprint2/progress.md` 中补充 Sprint 2 本地运行注意事项。
- [x] 运行后端测试，确认新增依赖配置不破坏现有测试。
