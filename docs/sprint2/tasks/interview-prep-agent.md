# Sprint 2 Interview Prep ReAct Agent 任务

状态：已完成

## 目标

用轻量 ReAct 生成 JD 相关问题和简历深挖问题，并给出结合 JD 与经历的完整示范回答。

## 依赖

- `docs/sprint2/improve.md`
- `docs/sprint2/agent-tools-trace.md`

## 完成标准

- Agent 使用 ReAct，最多 3 轮。
- 输出分为 `JD 相关问题` 和 `简历深挖问题`。
- JD 要求较多时生成 3-4 条，否则 1-2 条。
- 项目/实习内容较多时生成 3-4 条，否则 1-2 条。
- 每个问题有完整示范回答。
- 回答引用相关经历，但不展示 evidence ID。

## 最小任务清单

- [x] 创建 Interview Prep Agent 模块。
- [x] 使用 LangGraph `create_react_agent` 组装轻量 ReAct agent。
- [x] 只暴露 `get_high_priority_jd_requirements`、`get_matched_project_and_internship_evidence`、`draft_answer` 三个工具。
- [x] 设置最大迭代轮数为 3。
- [x] 输出 schema 区分 `jd_questions` 和 `resume_deep_dive_questions`。
- [x] prompt 要求完整示范回答，不生成模板化 walkthrough 建议。
- [x] prompt 要求项目问题侧重个人职责、技术难点、结果和复盘。
- [x] prompt 要求实习问题侧重技术、工作内容和成果。
- [x] 编写测试：JD 高优先级要求进入 JD 相关问题。
- [x] 编写测试：项目/实习证据进入简历深挖问题。
- [x] 编写测试：回答不展示 evidence ID。
- [x] 编写测试：3 轮失败后 workflow 返回失败。
