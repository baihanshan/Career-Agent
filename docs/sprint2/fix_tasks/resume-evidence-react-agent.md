# Resume Evidence ReAct Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Replace the fixed retrieval loop with a real LLM ReAct Agent that selects and semantically validates the smallest relevant evidence set for every JD requirement.

**Architecture:** The Agent uses structured search, experience inspection, semantic comparison, and reranking tools. Its Pydantic final output is validated against the evidence allowlist and support-state consistency rules.

**Tech Stack:** LangGraph `create_react_agent`, langchain-core tools, Pydantic v2, BGE/Chroma, pytest Fake ChatModel.

---

状态：已完成

## 依赖

- `react-model-runtime.md`
- `domain-models.md`
- `experience-structure.md`
- `requirement-semantics.md`
- `structured-agent-tools.md`
- `quality-gates.md`
- `docs/sprint2/fix_solution.md` 第 8 节

## 文件

- 重写：`backend/app/workflow/resume_evidence_agent.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`backend/app/workflow/service.py`
- 修改：`backend/app/workflow/state.py`
- 修改：`backend/tests/test_resume_evidence_agent.py`
- 新增：`backend/tests/fixtures/resume_evidence_react_calls.json`

## 最小任务

- [x] 编写失败测试：Agent 实际产生 search tool call，并根据首轮 insufficient 观察继续调用 get_experience/compare 工具。
- [x] 编写失败测试：Python 基础能力可由多个项目形成 indirect support，不能被判 missing。
- [x] 编写失败测试：多模态实习对多模态领域要求形成 direct support。
- [x] 编写失败测试：education/other 不能因为非 skill 就提前结束检索。
- [x] 编写失败测试：Agent 生成未知 evidence ID 时收到质量反馈并重试，三次失败返回受控错误。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py`，确认新行为失败。
- [x] 将 Agent prompt 改为工具驱动语义检索，禁止仅按 section 或分数下结论。
- [x] 使用 `create_react_agent` 和注入 ChatModel 运行，不再调用固定 `_section_filter_for_step` 循环。
- [x] 解析 final output 为 `EvidenceSelection[]`，更新 `retrieved_evidence`、`evidence_selections` 和 `allowed_evidence_ids`。
- [x] 接入 allowlist、支持状态一致性和重复 chunk 门禁，最多重试三次。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_retrieval.py backend/tests/test_match_scoring.py`。
- [x] 已生成提交命令：`git commit -m "feat: upgrade resume evidence to LLM ReAct"`，由用户确认后执行。

## 验证记录

- RED：新测试确认旧 Agent 不接受 ChatModel，仍运行固定检索循环。
- GREEN：Resume Evidence、retrieval、match scoring 与 workflow node 测试共 36 项通过。
- 回归：完整后端测试共 237 项通过。

## 完成标准

- Workflow 中运行的是真实 tool-calling Agent。
- 每个 requirement 都有结构化支持关系。
- 相似但不支持的证据不会被当作强匹配。
