# Sprint 2 Workflow Orchestrator 任务

状态：已完成

## 目标

将现有 LangGraph 固定流程升级为 Sprint 2 多 Agent 主流程，保持稳定编排，同时接入局部 ReAct 子 Agent。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/workflow/graph.py`
- `backend/app/workflow/nodes.py`
- `backend/app/workflow/state.py`

## 完成标准

- 主流程固定，不让 Coordinator 自由 ReAct。
- 接入 JD Analyst、Resume Evidence ReAct、Match Strategist、Resume Bullet、Interview Prep ReAct、Risk Auditor ReAct。
- 关键 ReAct Agent 失败时整个分析失败。
- 前端收到用户友好错误。
- 后台日志记录具体 Agent 失败原因。

## 最小任务清单

- [x] 更新 `WORKFLOW_NODE_ORDER` 为 Sprint 2 Agent 顺序。
- [x] 新增节点：`jd_analyst`。
- [x] 新增节点：`resume_evidence_agent`。
- [x] 新增节点：`match_strategist`。
- [x] 新增节点：`resume_bullet_agent`。
- [x] 新增节点：`interview_prep_agent`。
- [x] 新增节点：`risk_auditor_agent`。
- [x] 删除或替换旧 `write_application` 中 cover letter 输出路径。
- [x] 确保 collection cleanup 在成功和失败时都会执行。
- [x] 为 Agent 失败定义内部错误 code 和用户友好 message。
- [x] 编写集成测试：成功 workflow 返回 Sprint 2 模块。
- [x] 编写集成测试：Resume Evidence Agent 失败会终止 workflow。
- [x] 编写集成测试：collection 在失败时也会清理。
