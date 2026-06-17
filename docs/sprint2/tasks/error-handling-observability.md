# Sprint 2 Error Handling 与 Observability 任务

## 目标

实现质量优先错误策略：关键 ReAct Agent 失败时终止分析，前端展示友好提示，后台保留具体失败原因和 trace。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/core/errors.py`
- `backend/app/workflow/nodes.py`
- `backend/app/main.py`

## 完成标准

- ReAct Agent 失败不会降级返回低质量结果。
- 前端错误信息面向用户。
- 后台日志包含 agent 名称、失败工具、失败原因、trace 摘要。
- 不把隐藏推理或完整 prompt 暴露给前端。

## 最小任务清单

- [ ] 新增 Agent 失败错误 code。
- [ ] 新增 collection cleanup 失败 warning。
- [ ] 将内部 agent failure 转换为用户友好 message。
- [ ] 在后台日志记录 agent 名称、工具名、错误摘要。
- [ ] 确保 API response 不包含 API key、完整 prompt 或隐藏推理。
- [ ] 编写测试：前端错误 message 不含技术栈堆栈。
- [ ] 编写测试：后台日志包含 agent 名称。
- [ ] 编写测试：关键 Agent 失败时不会返回 partial result。

