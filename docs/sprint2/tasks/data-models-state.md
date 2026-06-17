# Sprint 2 Data Models 与 State 任务

## 目标

扩展后端 Pydantic schema 和 LangGraph state，使系统能表达结构化简历 section、多 Agent 输出、agent trace、用户友好错误和 Sprint 2 前端模块。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/api/schemas.py`
- `backend/app/workflow/state.py`

## 完成标准

- 支持 `internship`、`project`、`skill`、`education`、`other` section 类型。
- 支持 structured resume sections、match strategy、agent traces、risk report。
- 移除面向前端展示的 cover letter 字段。
- 后端内部仍保留 evidence 引用。
- 前端不展示 evidence table，但后端可用于 grounding、风险评估和 debug trace。

## 最小任务清单

- [ ] 新增 `ResumeSection` schema，包含 `section_type`、`section_title`、`content`。
- [ ] 新增 `ResumeSectionMetadata` schema，包含 `company_name`、`role_title`、`project_name`、`technologies`。
- [ ] 新增 `AgentTrace` schema，包含 agent 名称、工具名、参数摘要、观察摘要、最终决策摘要。
- [ ] 新增 `MatchStrategy` schema，用于记录高价值项目/实习证据排序结果。
- [ ] 新增 Sprint 2 `ResumeBullet` 输出约束：固定 3 条，内部保留 evidence 引用。
- [ ] 新增 Sprint 2 `InterviewPrep` schema，区分 `jd_questions` 和 `resume_deep_dive_questions`。
- [ ] 新增 Sprint 2 `RiskReport` schema，最多 3 条风险，隐藏内部 requirement ID。
- [ ] 从前端响应 schema 中移除面向 UI 的 `cover_letter` 展示字段。
- [ ] 在 workflow state 中加入 `structured_resume_sections`、`match_strategy`、`risk_report`、`agent_traces`。
- [ ] 编写 schema 测试，覆盖 section 类型、risk report 数量限制和 trace shape。

