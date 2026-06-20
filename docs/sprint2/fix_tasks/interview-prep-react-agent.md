# Interview Prep ReAct Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Generate realistic JD technical questions, concise resume deep dives, and natural evidence-grounded answers with a real LLM ReAct Agent.

**Architecture:** One Agent invocation produces two typed question groups with separate instructions. It inspects interviewable requirements and ExperienceRecords, drafts answer plans, then passes professional-question, evidence, duplication, and copy-ratio gates.

**Tech Stack:** LangGraph `create_react_agent`, structured tools, Pydantic v2, Fake ChatModel fixtures, pytest.

---

状态：已完成

## 依赖

- `resume-evidence-react-agent.md`
- `requirement-semantics.md`
- `experience-structure.md`
- `structured-agent-tools.md`
- `quality-gates.md`
- `public-output-boundary.md`
- `docs/sprint2/fix_solution.md` 第 9 节

## 文件

- 重写：`backend/app/workflow/interview_prep_agent.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`backend/app/workflow/domain_models.py`
- 修改：`backend/app/workflow/state.py`
- 修改：`backend/tests/test_interview_prep_agent.py`
- 新增：`backend/tests/fixtures/interview_prep_react_calls.json`

## 最小任务

- [x] 编写失败测试：硕士/博士 `document_check` requirement 不生成 JD 问题。
- [x] 编写失败测试：Python/算法要求生成带场景、约束和权衡的专业问题，不包含“你如何满足”。
- [x] 编写失败测试：多模态 requirement 生成平台、数据、模型、评估或性能方向问题。
- [x] 编写失败测试：项目问题只使用项目名或一句摘要，不拼接完整 snippet。
- [x] 编写失败测试：同一经历的多题使用不同 focus，且问题语义不重复。
- [x] 编写失败测试：答案包含 direct answer、技术权衡、验证方式和证据事实，但复制率低于门禁阈值。
- [x] 编写失败测试：ID 泄露、未知 evidence、模板复述或高复制率触发带反馈重试。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_interview_prep_agent.py`，确认新测试失败。
- [x] 扩展 internal question output：question_type、competencies_tested、target_requirement_ids、answer_plan、supporting_evidence_ids。
- [x] 使用真实 `create_react_agent` 调用 interviewable requirement、get_experience 与 requirement evidence 工具，并由结构化 answer plan 和确定性门禁完成 draft/inspect。
- [x] 删除固定 `_deep_dive_question` 和 `_sample_answer` 运行路径，避免新旧模板并存。
- [x] 接入 question/answer/public gates 和三次重试。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_interview_prep_agent.py backend/tests/test_workflow_nodes.py backend/tests/test_public_output.py`。
- [x] 已生成提交命令：`git commit -m "feat: upgrade interview prep to LLM ReAct"`，由用户确认后执行。

## 验证记录

- RED：13 项新测试确认旧 Agent 不接受 ChatModel、节点未使用运行时 ReAct model，且仍依赖固定问题与答案模板。
- GREEN：Interview Prep、workflow node 与 public output 专项测试共 33 项通过。
- 回归：完整后端测试通过；默认本地模型按架构、调试、评估和迁移/反思轮换问题焦点。

## 完成标准

- JD 问题具有真实技术面试价值。
- 简历问题简洁定位经历并进行专业深挖。
- 答案重新组织语言，不复制整段简历。
