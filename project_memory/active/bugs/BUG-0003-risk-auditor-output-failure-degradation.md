---
id: BUG-0003
title: Risk Auditor output failures should not fail the whole analysis
status: active
level: P1
tags:
  - backend
  - react-agent
  - risk-auditor-agent
  - quality-gate
  - graceful-degradation
use_when: Debugging intermittent `/analysis` failures with `REACT_QUALITY_GATE_FAILED` or `REACT_OUTPUT_PARSE_ERROR` at `risk_auditor_agent`.
updated: 2026-07-04
---

# BUG-0003：Risk Auditor 输出失败不应阻断整次分析

## 症状

真实模型调用 `/analysis` 时偶发失败，API 返回：

```text
REACT_QUALITY_GATE_FAILED
Risk audit could not be completed safely.
```

或：

```text
REACT_OUTPUT_PARSE_ERROR
The model did not return valid structured output.
```

同一输入有时成功，有时失败。

## 根因

- `RiskAuditorAgent` 是主流程最后的风险审计增强节点。
- 它要求模型在最终输出前完成一组工具调用，并通过确定性质量门禁。
- 真实模型偶发少调用工具、改变 JSON 包装形态或产出无法解析的最终消息时，会在 3 次重试后抛 `RiskAuditorAgentError`。
- `nodes.audit_risks()` 原先会把该错误写入 `state.errors`，导致后续 `public_output_gate` 跳过，整次 `/analysis` 返回 failed。
- 但此时 JD 分析、证据检索、匹配、简历要点、面试准备和基础 evaluation report 通常已经完成；Risk Auditor 的输出失败可以降级为 warning，而不是阻断主体结果。

## 修复

- `nodes.audit_risks()` 对 `risk_auditor_agent` 的以下可控输出失败降级：
  - `REACT_OUTPUT_PARSE_ERROR`
  - `REACT_QUALITY_GATE_FAILED`
- 降级后不写入 `state.errors`，而是追加 `ProcessingWarning`：

```text
Risk audit could not be completed safely; showing baseline evaluation warnings instead.
```

- `risk_report` 保持为空，前端可继续展示 `evaluation_report.risk_summary`、coverage gaps 和 grounding warnings 作为基础风险提示。
- 前置关键 agent，例如 `resume_evidence_agent`，仍保持原有 failed 行为，不受该降级影响。

## 验证

已执行：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_error_handling.py::test_risk_auditor_output_failure_degrades_to_processing_warning
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_error_handling.py backend/tests/test_risk_auditor_agent.py backend/tests/test_workflow_orchestrator.py
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。完整后端测试仅保留既有 `StarletteDeprecationWarning`。

## 后续

如果用户复测仍出现 failed，优先看错误是否来自 `resume_evidence_agent` 或 `interview_prep_agent`。本次降级只覆盖 `risk_auditor_agent` 的输出不可用问题。
