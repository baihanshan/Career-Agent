# ReAct Workflow Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Wire all three real ReAct Agents, public projection, quality retries, errors, and safe traces into the fixed LangGraph workflow.

**Architecture:** Preserve deterministic top-level orchestration while injecting ChatModel and tools through `WorkflowServices`. Add a public-output gate before final response and remove obsolete fixed-template execution paths.

**Tech Stack:** LangGraph StateGraph, Pydantic v2, FastAPI, pytest.

---

状态：待实现

## 依赖

- `resume-evidence-react-agent.md`
- `resume-bullet-safety.md`
- `interview-prep-react-agent.md`
- `risk-auditor-react-agent.md`
- `public-output-boundary.md`
- `quality-gates.md`
- `docs/sprint2/fix_solution.md` 第 5、6、13、15 节

## 文件

- 修改：`backend/app/workflow/graph.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`backend/app/workflow/service.py`
- 修改：`backend/app/workflow/state.py`
- 修改：`backend/app/core/errors.py`
- 修改：`backend/tests/test_workflow_orchestrator.py`
- 修改：`backend/tests/test_workflow_integration.py`
- 修改：`backend/tests/test_error_handling.py`
- 修改：`backend/tests/test_observability.py`

## 最小任务

- [ ] 编写失败测试：`WorkflowServices` 为三个 Agent 注入同一分析配置下的 ReAct ChatModel 和 structured tools。
- [ ] 编写失败测试：实际 graph 运行会出现三个 Agent 的真实 tool-call trace，而不是固定模板 trace。
- [ ] 编写失败测试：public output gate 在 `finalize_response` 前运行，失败时不返回 partial result。
- [ ] 编写失败测试：模型不支持 tool calling、工具失败、输出解析失败、质量门禁失败和证据违规映射到稳定错误码。
- [ ] 编写失败测试：API key、完整 Prompt、隐藏推理和完整简历不会进入日志或 response。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_workflow_orchestrator.py backend/tests/test_workflow_integration.py`，确认失败。
- [ ] 扩展 `WorkflowServices`：`react_model`、三个 Agent 实例、quality gate 和 public projector。
- [ ] 在 graph 中加入 `public_output_gate` 节点，顺序固定为 risk auditor 之后、finalize 之前。
- [ ] 将每个 Agent 的三次重试限定在自身节点内；顶层 graph 不重复执行已成功节点。
- [ ] 删除 Resume Evidence、Interview Prep、Risk Auditor 的旧固定模板运行分支。
- [ ] 保留 Chroma collection finally cleanup，并确保 Agent 异常同样触发 cleanup。
- [ ] 运行 `env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_workflow_orchestrator.py backend/tests/test_workflow_integration.py backend/tests/test_error_handling.py backend/tests/test_observability.py`。
- [ ] 提交：`git commit -m "feat: integrate real ReAct Agents into workflow"`。

## 完成标准

- 三个 Agent 均在生产 workflow 中调用 LLM tools。
- 质量失败不会泄露半成品。
- 顶层执行顺序、错误路由和资源清理保持确定性。

