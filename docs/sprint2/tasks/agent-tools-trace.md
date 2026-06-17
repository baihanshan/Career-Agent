# Sprint 2 Agent Tools 与 Trace 任务

## 目标

为 ReAct 子 Agent 提供受控工具集，并记录可折叠展示的 agent trace。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/workflow/state.py`
- `backend/app/retrieval/service.py`

## 完成标准

- Resume Evidence Agent、Interview Prep Agent、Risk Auditor Agent 都只能调用白名单工具。
- 每个 ReAct Agent 最多 3 轮。
- 工具调用 trace 被记录到 state。
- 前端默认隐藏 trace，可在“分析过程详情”中展开。
- 不展示完整隐藏推理，只展示工具调用和决策摘要。

## 最小任务清单

- [ ] 定义 `AgentToolResult` 数据结构，包含工具名、参数摘要、返回摘要、状态。
- [ ] 定义 `AgentTrace` 数据结构，包含 agent 名称、步骤列表、最终决策摘要。
- [ ] 实现 trace recorder，用于各 ReAct Agent 写入 state。
- [ ] 实现 `search_resume_evidence(query, section_filter, top_k)` 工具。
- [ ] 实现 `get_resume_section(section_type)` 工具。
- [ ] 实现 `rerank_evidence(requirement, evidence_items)` 工具。
- [ ] 实现 `get_high_priority_jd_requirements()` 工具。
- [ ] 实现 `get_matched_project_and_internship_evidence()` 工具。
- [ ] 实现 `draft_answer(question, evidence, jd_requirement)` 工具。
- [ ] 实现 `check_requirement_coverage(requirement)` 工具。
- [ ] 实现 `find_resume_vague_claims()` 工具。
- [ ] 实现 `check_generated_claim_grounding(claim)` 工具。
- [ ] 实现 `rank_top_risks(risks, limit=3)` 工具。
- [ ] 编写测试：每个工具只返回摘要，不泄露完整 prompt。
- [ ] 编写测试：trace 能序列化给前端。

