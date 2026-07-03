# Sprint 2 JD Analyst Agent 任务

状态：已完成

## 目标

将 JD 解析封装为稳定的专业 Agent 节点，输出高质量结构化岗位要求，不使用 ReAct。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/llm/prompts.py`
- `backend/app/llm/structured_outputs.py`
- `backend/app/workflow/nodes.py`

## 完成标准

- 能抽取 hard skill、soft skill、responsibility、qualification、nice_to_have。
- 能标记 high、medium、low importance。
- 输出保留 JD 原文或可读摘要，供风险提示展示。
- 不展示 `req_1` 这类内部 ID 给前端用户。

## 最小任务清单

- [x] 更新 JD extraction prompt，要求保留用户可读的 JD requirement text。
- [x] 保留内部 requirement_id，但前端展示使用 requirement text。
- [x] 让 parser 继续兼容模型字段变体。
- [x] 为 high priority requirement 增加明确判断标准。
- [x] 编写测试：高优先级 JD 要求能被标记为 `high`。
- [x] 编写测试：JD requirement text 可用于前端风险提示。
- [x] 编写测试：模型返回 wrapper object 时仍能解析。
