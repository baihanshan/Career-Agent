# Risk Auditor ReAct Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Generate only evidence-consistent, semantically accurate, actionable risks using a real LLM ReAct Agent.

**Architecture:** Separate resume coverage, evidence strength, and bullet coverage. The Agent inspects structured evidence and numeric claims, reasons over OR requirements, and emits internal risks that must pass deterministic consistency gates before public projection.

**Tech Stack:** LangGraph `create_react_agent`, structured tools, Pydantic v2, numeric grounding, pytest Fake ChatModel.

---

状态：待实现

## 依赖

- `resume-evidence-react-agent.md`
- `numeric-grounding.md`
- `structured-agent-tools.md`
- `quality-gates.md`
- `public-output-boundary.md`
- `docs/sprint2/fix_solution.md` 第 10 节

## 文件

- 重写：`backend/app/workflow/risk_auditor_agent.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`backend/app/workflow/service.py`
- 修改：`backend/app/api/schemas.py`
- 修改：`backend/tests/test_risk_auditor_agent.py`
- 新增：`backend/tests/fixtures/risk_auditor_react_calls.json`

## 最小任务

- [ ] 编写失败测试：多个 Python 项目形成 indirect support 时不得生成“不会 Python”风险。
- [ ] 编写失败测试：语义分割支持 ML/CV，NLP/RAG 支持 NLP，多模态实习支持多模态领域。
- [ ] 编写失败测试：“NLP 或多模态至少一个”满足任一分支即不得判整体 missing。
- [ ] 编写失败测试：未进入三条 bullet 但完整简历有强证据时，只记录 bullet coverage，不生成能力缺失风险。
- [ ] 编写失败测试：无真实风险时允许返回空列表，不凑满三条。
- [ ] 编写失败测试：risk public 文本不出现 ID，internal supporting evidence 通过白名单。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_risk_auditor_agent.py`，确认新行为失败。
- [ ] 将 tools 分为 requirement、evidence、experience、numeric、bullet coverage 和 risk ranking 六类结构化观察。
- [ ] 使用真实 `create_react_agent` 替换固定 `_candidate_risks` 运行路径。
- [ ] final output 使用 internal risk schema，接入 evidence/risk consistency/public gates 和三次重试。
- [ ] 保留确定性 severity 排序与最多三条限制，但不制造候选风险。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_risk_auditor_agent.py backend/tests/test_evaluator.py backend/tests/test_public_output.py`。
- [ ] 提交：`git commit -m "feat: upgrade risk auditor to LLM ReAct"`。

## 完成标准

- 风险基于完整简历语义和证据强度。
- 不再混淆简历覆盖与 bullet 选择。
- 风险与证据矛盾时确定性门禁会阻止展示。

