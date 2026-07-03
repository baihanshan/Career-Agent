# Sprint 2 Testing Fixtures 与 QA 任务

状态：已完成

## 目标

为 Sprint 2 架构提供稳定测试样例，覆盖结构化简历、BGE/Chroma mock、ReAct 工具调用、最终前端模块。

## 依赖

- `docs/sprint2/improve.md`
- `backend/tests/fixtures`
- `backend/tests`
- `frontend/scripts/verify-structure.mjs`

## 完成标准

- 有包含项目、实习、技能、教育的 sample profile。
- 有包含多种要求优先级的 sample JD。
- 有 fake BGE embedding 和 fake Chroma 测试路径。
- 有 ReAct 工具调用 fixture。
- 有完整 Sprint 2 workflow 集成测试。

## 最小任务清单

- [x] 新增 Sprint 2 sample profile，包含项目、实习、技能、教育。
- [x] 新增 Sprint 2 sample JD，包含 high/medium/low 要求。
- [x] 新增 fake BGE embedding fixture。
- [x] 新增 fake Chroma vector store fixture。
- [x] 新增 Resume Evidence Agent 工具调用 fixture。
- [x] 新增 Interview Prep Agent 工具调用 fixture。
- [x] 新增 Risk Auditor Agent 工具调用 fixture。
- [x] 编写集成测试：最终结果不包含 cover letter。
- [x] 编写集成测试：最终结果不展示 evidence table。
- [x] 编写集成测试：简历要点来自项目/实习而不是技能列表。
- [x] 编写集成测试：风险提示最多 3 条且不含内部 ID。
- [x] 编写集成测试：agent trace 可序列化。
