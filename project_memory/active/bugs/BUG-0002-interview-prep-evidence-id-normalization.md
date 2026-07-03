---
id: BUG-0002
title: DeepSeek interview_prep_agent emits unstable supporting evidence IDs
status: active
level: P1
tags:
  - backend
  - deepseek
  - react-agent
  - interview-prep-agent
  - evidence-allowlist
use_when: Debugging `/analysis` failures where frontend shows invalid evidence, backend returns `REACT_EVIDENCE_VIOLATION`, or `interview_prep_agent` fails at `quality_gate`.
updated: 2026-07-01
---

# BUG-0002：DeepSeek interview_prep_agent 生成不稳定 supporting evidence ID

## 症状

用户使用 DeepSeek 复测 `/analysis` 后，前端显示：

```text
生成结果引用了无效证据，系统已阻止展示。
```

后端日志显示最终失败阶段为：

```text
agent=interview_prep_agent tool=quality_gate reason=Interview Prep Agent failed deterministic quality validation after 3 attempts.
```

同一批日志还显示 DeepSeek 常在 JSON 前添加自然语言前缀，例如：

```text
Now I have all the evidence needed. Let me compile the final selections. {"selections":[...]}
```

## 根因

- `interview_prep_agent` 会在每个 attempt 开始时清空 `allowed_evidence_ids`，要求本轮工具调用重新把 evidence 加入 allowlist。
- DeepSeek 生成的面试题可能漏填 `supporting_evidence_ids`，或使用不在本轮 allowlist 中的内部 evidence id。
- 这些 ID 是内部追踪字段，不展示给用户；但后端质量门禁会严格校验它们，因此触发 `UNKNOWN_EVIDENCE_ID` 并归类为 `REACT_EVIDENCE_VIOLATION`。
- 另外，ReAct agent fallback parser 原来只接受纯 JSON 或 fenced JSON，不接受自然语言前缀后的 JSON，导致真实模型输出更容易进入 parse retry。

## 修复

- 新增 `backend/app/workflow/json_outputs.py`，提供 `parse_json_payload_from_text`，支持：
  - 纯 JSON；
  - fenced JSON；
  - 自然语言前缀后出现的第一个可解析 JSON object/array。
- `resume_evidence_agent`、`interview_prep_agent`、`risk_auditor_agent` 统一使用该 helper 解析最终 AI message。
- `interview_prep_agent` 在质量门禁前调用 `_normalize_supporting_evidence_ids`：
  - 保留本轮工具 allowlist 中的真实 evidence id；
  - 如果模型漏填或编造 ID，则根据 `target_requirement_ids` 选择同 requirement 的已允许 evidence；
  - 对 deep-dive question，再根据 `experience_id` 的 raw chunks 选择已允许 evidence；
  - 只会写入本轮工具已允许的真实 evidence id，不放行未知 ID。
- 2026-07-01 后续补丁：真实 DeepSeek 日志确认失败阶段仍可能是 `agent=interview_prep_agent tool=quality_gate`。当模型漏填/错填 JD question 的 `target_requirement_ids`，且 `supporting_evidence_ids` 不在 allowlist 时，`_normalize_supporting_evidence_ids` 会从本轮 allowed evidence 回填 supporting evidence，并反推 interviewable requirement id，避免内部追踪字段导致 `REACT_EVIDENCE_VIOLATION`。

## 验证

已执行：

```bash
conda run -n carrer_agent pytest -q backend/tests/test_interview_prep_agent.py::test_prefixed_json_final_output_is_parsed_without_retry backend/tests/test_interview_prep_agent.py::test_unknown_supporting_evidence_ids_are_normalized_from_target_requirement
conda run -n carrer_agent pytest -q backend/tests/test_interview_prep_agent.py
conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_interview_prep_agent.py backend/tests/test_risk_auditor_agent.py
env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_interview_prep_agent.py
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_interview_prep_agent.py backend/tests/test_risk_auditor_agent.py backend/tests/test_public_output.py
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。完整后端测试仅保留既有 `StarletteDeprecationWarning`。

## Evidence

- 用户日志显示 `agent=interview_prep_agent tool=quality_gate`，前端错误文案对应 `REACT_EVIDENCE_VIOLATION`。
- 代码检查确认 `_validate_prep` 对 `interview_prep.questions.*.supporting_evidence_ids` 调用 `validate_evidence_allowlist`，空 ID 或非 allowlist ID 都会生成 `UNKNOWN_EVIDENCE_ID`。
- 回归测试 `test_unknown_supporting_evidence_ids_are_normalized_from_target_requirement` 覆盖未知 supporting evidence id 规范化。
- 回归测试 `test_prefixed_json_final_output_is_parsed_without_retry` 覆盖自然语言前缀 + JSON 的真实模型输出形态。

## 后续

需要用户用真实 DeepSeek、同一份简历/JD 复测。如果还有失败，优先根据 `agent=... tool=...` 判断是否进入 risk auditor 或 public output gate 阶段。
