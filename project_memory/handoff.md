# 交接记录

## 当前上下文

更新日期：2026-07-01

### 当前目标

- 已完成：修复 DeepSeek 下 `interview_prep_agent` 因内部 supporting evidence ID 不稳定触发 `REACT_EVIDENCE_VIOLATION` 的问题，并增强 ReAct JSON parser 兼容“自然语言前缀 + JSON”输出。

### 当前项目状态

- 生产代码已无 `create_react_agent` / `langgraph.prebuilt` 引用；依赖改为显式 `langchain>=1.0.0`，移除直接 `langgraph-prebuilt` 依赖。OpenAI provider 保留 Pydantic `response_format`，DeepSeek/openai-compatible provider 改走 JSON prompt + fallback parser。三个 ReAct agent 共享 `parse_json_payload_from_text`，可解析纯 JSON、fenced JSON、自然语言前缀后的 JSON。`interview_prep_agent` 会把内部 `supporting_evidence_ids` 规范化为本轮工具 allowlist 中的真实 evidence id。完整后端测试在 `RETRIEVAL_BACKEND=fake` 下通过。

### 最近变更

- 2026-07-01：用户复现日志显示 `interview_prep_agent tool=quality_gate`，前端报“生成结果引用了无效证据”。修复为：解析带自然语言前缀的 JSON；在面试准备校验前按 target requirement / experience chunks 规范化 supporting evidence id。
- 2026-06-30：用户复现日志显示三次 `GraphRecursionError: Recursion limit of 10 reached`；修复为动态递归预算 `max(max_steps * 2 + 4, requirement_count * 4 + 12, 30)`，并新增 `REACT_RECURSION_LIMIT_ERROR`。
- 2026-06-30：`ResumeEvidenceAgent` 在 `_parse_final_selections` 异常时增加脱敏 warning 日志，并补充 caplog 回归测试。
- 2026-06-30：更新 `AGENTS.md`，补充 CareerPilot Agent 仓库结构说明。
- 2026-06-30：`ResumeEvidenceAgent`、`InterviewPrepAgent`、`RiskAuditorAgent` 改用 `langchain.agents.create_agent(system_prompt=..., response_format=...)`。
- 2026-06-30：`react_response_format` 改为只对 OpenAI provider 返回 Pydantic schema；三个 Agent prompt 增加短 JSON example。

### 未解决问题

- 需要用户用真实 DeepSeek、同一份简历/JD 复测。如果仍失败，查看是否是新的 agent 阶段错误，还是 remaining schema/quality gate 问题。

### 下一步建议

- 让用户重启后端并复测。如果仍失败，请用户贴 `agent=...`、`REACT_*`、`UNKNOWN_*`、`*_structured_output_parse_failed` 相关日志行，避免贴 API key 和完整简历。

### 相关记忆条目

- `project_memory/active/decisions/ADR-0001-use-langchain-create-agent.md`
- `project_memory/active/bugs/BUG-0001-resume-evidence-recursion-limit.md`
- `project_memory/active/bugs/BUG-0002-interview-prep-evidence-id-normalization.md`

## 最近交接记录
