# Sprint 2 Resume Evidence ReAct Agent 任务

## 目标

用 LangGraph `create_react_agent` 实现 Resume Evidence Agent，使其能多轮检索并优先找到项目和实习证据。

## 依赖

- `docs/sprint2/improve.md`
- `docs/sprint2/embedding-chroma.md`
- `docs/sprint2/agent-tools-trace.md`

## 完成标准

- Agent 使用 ReAct，最多 3 轮。
- 首轮检索只命中 skill 时，会继续检索 project/internship。
- 返回 evidence items 按项目/实习优先和 JD 匹配度排序。
- 如果 3 轮内无法找到可用证据，整个分析失败。
- 失败信息前端友好，后台记录具体原因。

## 最小任务清单

- [ ] 创建 Resume Evidence Agent 模块。
- [ ] 使用 LangGraph `create_react_agent` 组装 agent。
- [ ] 只暴露 `search_resume_evidence`、`get_resume_section`、`rerank_evidence` 三个工具。
- [ ] 设置最大迭代轮数为 3。
- [ ] prompt 明确要求 project/internship 优先，skill 仅辅助。
- [ ] prompt 明确如果结果只有 skill，需要继续查项目/实习。
- [ ] 输出结构化 evidence items。
- [ ] 记录 agent trace。
- [ ] 编写测试：技能命中后继续检索项目。
- [ ] 编写测试：项目证据排序高于技能证据。
- [ ] 编写测试：3 轮失败后 workflow 返回失败。

