# Structured Agent Tools and Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Replace summary-only pseudo tools with structured LangChain tools while retaining safe trace summaries.

**Architecture:** A tool returns typed data to the Agent and separately records a redacted summary. Each Agent receives only its allowlisted tools.

**Tech Stack:** Python 3.11, langchain-core StructuredTool, Pydantic v2, pytest.

---

状态：待实现

## 依赖

- `react-model-runtime.md`
- `domain-models.md`
- `experience-structure.md`
- `requirement-semantics.md`
- `docs/sprint2/fix_solution.md` 第 6.3、8.2、10.2、15 节

## 文件

- 新增：`backend/app/workflow/react_tools.py`
- 修改：`backend/app/workflow/agent_tools.py`
- 修改：`backend/app/workflow/state.py`
- 新增：`backend/tests/test_structured_react_tools.py`
- 修改：`backend/tests/test_agent_tools_trace.py`

## 最小任务

- [ ] 编写失败测试：`search_resume_evidence` 返回结构化 evidence 列表而非仅摘要字符串。
- [ ] 编写失败测试：`get_experience` 返回单个 ExperienceRecord，未知 ID 返回受控 tool error。
- [ ] 编写失败测试：Resume Evidence、Interview Prep、Risk Auditor 各自只能访问设计允许的工具。
- [ ] 编写失败测试：trace 只包含参数摘要和返回摘要，不包含 API key、完整 Prompt、隐藏推理或完整简历。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_structured_react_tools.py`，确认失败。
- [ ] 使用 Pydantic args schema 定义 structured tools，返回可 JSON 序列化的 typed payload。
- [ ] 实现 `StructuredToolResult(data, trace_summary)` 适配和统一 tool error 映射。
- [ ] 更新 `TraceRecorder`，记录 tool 名、redacted arguments、redacted result、status 和 attempt number。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_structured_react_tools.py backend/tests/test_agent_tools_trace.py`，确认通过。
- [ ] 提交：`git commit -m "feat: add structured ReAct tools and safe traces"`。

## 完成标准

- LLM 能读取真实结构化工具结果。
- 工具 allowlist 在运行时强制执行。
- Trace 可观察但不泄露敏感信息。

