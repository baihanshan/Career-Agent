# Sprint 2 Risk Auditor ReAct Agent 任务

## 目标

用 ReAct 生成最多 3 条具体、可解释、可行动的风险提示，隐藏内部 requirement ID。

## 依赖

- `docs/sprint2/improve.md`
- `docs/sprint2/agent-tools-trace.md`
- `backend/app/evaluation/evaluator.py`

## 完成标准

- Agent 使用 ReAct，最多 3 轮。
- 风险提示最多 3 条。
- 风险按严重程度和求职影响排序。
- 每条风险包含风险标题、对应 JD 要求、简历现状、为什么有风险、建议如何补充。
- 风险类型支持 `JD 未覆盖`、`简历表述太泛`、`证据不足`、`生成内容可能夸大`。
- 前端不展示 `req_1` 等内部 ID。

## 最小任务清单

- [ ] 创建 Risk Auditor Agent 模块。
- [ ] 使用 LangGraph `create_react_agent` 组装 agent。
- [ ] 只暴露 `check_requirement_coverage`、`find_resume_vague_claims`、`check_generated_claim_grounding`、`rank_top_risks` 四个工具。
- [ ] 设置最大迭代轮数为 3。
- [ ] prompt 要求风险必须具体到 JD 要求和简历现状。
- [ ] prompt 要求优先分析项目和实习，不以技能列表为主要依据。
- [ ] 输出 schema 限制最多 3 条。
- [ ] 编写测试：不展示内部 requirement ID。
- [ ] 编写测试：重复泛化风险会被合并或丢弃。
- [ ] 编写测试：风险按严重程度和求职影响排序。
- [ ] 编写测试：3 轮失败后 workflow 返回失败。

