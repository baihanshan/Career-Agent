---
id: BUG-0001
title: DeepSeek resume_evidence_agent hits LangGraph recursion limit
status: active
level: P1
tags:
  - backend
  - deepseek
  - react-agent
  - resume-evidence-agent
  - langgraph
use_when: Debugging `/analysis` failures where DeepSeek ReAct agents loop on tools, hit `GraphRecursionError`, or return `REACT_RECURSION_LIMIT_ERROR` / `REACT_OUTPUT_PARSE_ERROR`.
updated: 2026-06-30
---

# BUG-0001：DeepSeek resume_evidence_agent 触发 LangGraph recursion limit

## 症状

用户使用 DeepSeek 配置运行 `/analysis` 时，前端显示“模型未生成有效的结构化结果”。后端业务响应起初为 `REACT_OUTPUT_PARSE_ERROR`。

加脱敏诊断日志后，用户复现得到：

```text
event=resume_evidence_structured_output_parse_failed attempt=1 exception=GraphRecursionError reason=Recursion limit of 10 reached without hitting a stop condition final_ai_message=[no agent result]
event=resume_evidence_structured_output_parse_failed attempt=2 exception=GraphRecursionError reason=Recursion limit of 10 reached without hitting a stop condition final_ai_message=[no agent result]
event=resume_evidence_structured_output_parse_failed attempt=3 exception=GraphRecursionError reason=Recursion limit of 10 reached without hitting a stop condition final_ai_message=[no agent result]
agent=resume_evidence_agent tool=structured_output reason=Resume Evidence Agent could not produce valid structured output.
```

## 根因

`ResumeEvidenceAgent` 原来传给 `create_agent.invoke` 的 `recursion_limit` 为：

```python
self.max_steps * 2 + 4
```

默认 `MAX_REACT_AGENT_STEPS = 3`，所以实际限制为 `10`。面对多个 JD requirement 时，DeepSeek 会持续调用 `get_resume_section`、`search_resume_evidence`、`compare_requirement_to_evidence` 等工具，尚未进入最终 JSON 输出就达到 LangGraph 图递归上限。因为没有最终 AI message，外层把它包装成了结构化输出解析失败。

## 修复

- `ResumeEvidenceAgent` 的 ReAct 递归预算改为动态值：

```python
max(max_steps * 2 + 4, requirement_count * 4 + 12, 30)
```

- system prompt 增加强停止条件：每个 requirement 有足够证据判断 strong/partial/missing 后不要继续追求完美证据。
- 单独捕获 `langgraph.errors.GraphRecursionError`，失败工具标记为 `recursion_limit`。
- 新增受控错误码 `REACT_RECURSION_LIMIT_ERROR`，工作流对用户返回更准确的消息。
- 保留脱敏诊断日志，继续帮助定位真实模型最终输出或无输出状态。

## 验证

已执行：

```bash
conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py::test_recursion_limit_scales_with_requirement_count backend/tests/test_resume_evidence_agent.py::test_graph_recursion_error_is_classified_separately backend/tests/test_error_handling.py::test_react_recursion_limit_failure_reports_the_actual_failure_stage
conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_error_handling.py
env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。完整后端测试仅保留既有 `StarletteDeprecationWarning`。

## Evidence

- 用户提供的脱敏日志显示三次 attempt 均为 `exception=GraphRecursionError`，原因是 `Recursion limit of 10 reached without hitting a stop condition`，且 `final_ai_message=[no agent result]`。
- 代码检查确认原 `ResumeEvidenceAgent` 使用 `config={"recursion_limit": self.max_steps * 2 + 4}`，默认值为 10。
- 回归测试 `test_recursion_limit_scales_with_requirement_count` 覆盖动态递归预算。
- 回归测试 `test_graph_recursion_error_is_classified_separately` 覆盖 `GraphRecursionError` 单独归类。
- 回归测试 `test_react_recursion_limit_failure_reports_the_actual_failure_stage` 覆盖工作流对新错误码的透传和用户消息。

## 后续

需要用户用真实 DeepSeek、同一份简历/JD 复测。如果仍失败，优先查看新日志是继续 `GraphRecursionError`，还是进入最终 `final_ai_message` 后的 JSON/schema 解析问题。
