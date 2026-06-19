# Sprint 2 总体进度

本文档用于新对话接续 Sprint 2 工作。每个模块的具体任务见同目录下对应 `<module-name>.md` 文件。

## 项目背景

CareerPilot Agent 是一个面向求职者的 agentic LLM application。用户输入个人职业材料和目标岗位 JD，系统基于真实材料生成岗位匹配摘要、简历要点、面试准备和风险提示。

MVP 已完成基础闭环：

- FastAPI 后端。
- Next.js 中文前端。
- Pydantic schema。
- LangGraph 固定 workflow。
- 用户可在 UI 输入 DeepSeek/OpenAI API Key。
- LLM 用于 JD 抽取、生成内容和评估。
- 当前检索仍是 fake token-count embedding + in-memory vector store。

Sprint 2 目标是升级为：

- 本地 `BAAI/bge-large-zh-v1.5` + `sentence-transformers` embedding。
- 本地持久化 Chroma。
- 每次分析独立 Chroma collection，分析完成后删除。
- LangGraph 固定主流程 + 局部 ReAct 子 Agent。
- 使用 `create_react_agent` 实现 Resume Evidence、Interview Prep、Risk Auditor。
- 删除求职信草稿和前端证据表展示。
- 保留内部 evidence 引用，用于 grounding、风险评估和 trace。
- 输出质量优先，关键 ReAct Agent 失败时整个分析失败。

## 关键产品决策

- 简历要点固定 3 条，优先项目和实习，不从技能列表单独生成。
- 实习要点需要包含公司名、项目内容、成果和技术栈。
- 项目要点需要包含项目名称、项目目标、个人贡献、技术栈、结果或可量化影响。
- 面试准备分为 `JD 相关问题` 和 `简历深挖问题`。
- 面试回答是完整示范回答，不展示 evidence ID，但引用相关经历。
- 风险提示最多 3 条，隐藏内部 requirement ID。
- Agent trace 默认隐藏在“分析过程详情”中，可展开查看。
- 前端不展示 cover letter。
- 前端不展示 evidence table。

## 推荐执行顺序

1. `project-setup.md`
2. `data-models-state.md`
3. `resume-structure.md`
4. `embedding-chroma.md`
5. `agent-tools-trace.md`
6. `jd-analyst-agent.md`
7. `resume-evidence-agent.md`
8. `match-strategist-agent.md`
9. `resume-bullet-agent.md`
10. `interview-prep-agent.md`
11. `risk-auditor-agent.md`
12. `workflow-orchestrator.md`
13. `frontend-output.md`
14. `error-handling-observability.md`
15. `testing-fixtures.md`
16. `pdf-resume-upload.md`

## 模块进度

- [x] `project-setup.md`：依赖、环境变量、BGE/Chroma 默认路径
- [x] `data-models-state.md`：Sprint 2 schema、workflow state、trace model
- [x] `resume-structure.md`：结构化简历 section 与 chunk metadata
- [x] `embedding-chroma.md`：BGE embedding、Chroma store、collection lifecycle
- [x] `agent-tools-trace.md`：ReAct 工具集与 trace 记录
- [x] `jd-analyst-agent.md`：JD 结构化分析节点
- [x] `resume-evidence-agent.md`：Resume Evidence ReAct Agent
- [x] `match-strategist-agent.md`：匹配策略与排序
- [x] `resume-bullet-agent.md`：3 条项目/实习优先简历要点
- [x] `interview-prep-agent.md`：轻量 ReAct 面试准备
- [x] `risk-auditor-agent.md`：ReAct top 3 风险评估
- [x] `workflow-orchestrator.md`：LangGraph Sprint 2 主流程
- [x] `frontend-output.md`：Sprint 2 前端展示模块
- [x] `error-handling-observability.md`：质量优先错误与日志策略
- [x] `testing-fixtures.md`：Sprint 2 fixtures、集成测试、QA
- [ ] `pdf-resume-upload.md`：文字型 PDF 上传、文本回填与纯文本简历标题识别

## 新对话启动提示

如果开启新对话，可以直接提供以下背景：

```text
项目路径：/Users/baihanshan/Desktop/Career Agent

当前任务：实现 Sprint 2 架构升级。请先阅读：
1. docs/sprint2/improve.md
2. docs/sprint2/progress.md
3. 当前要执行的模块任务文件

核心决策：
- 使用本地 BAAI/bge-large-zh-v1.5 + sentence-transformers。
- 模型缓存目录：/Users/baihanshan/Desktop/bge-models。
- 使用本地持久化 Chroma。
- Chroma 目录：/Users/baihanshan/Desktop/career-agent-chroma。
- 每次分析独立 collection，完成后删除。
- 主流程继续用 LangGraph 固定编排。
- Resume Evidence、Interview Prep、Risk Auditor 使用 LangGraph create_react_agent。
- 所有 ReAct Agent 最多 3 轮。
- 关键 ReAct Agent 失败时整个分析失败。
- 删除求职信草稿和前端证据表展示。
- 内部保留 evidence 引用。
```

## 总体验收

- [x] 用户输入简历和 JD 后，系统使用 BGE + Chroma 检索项目/实习证据。
- [x] 简历要点来自项目/实习，固定 3 条，按 JD 匹配度排序。
- [x] 面试准备分为 JD 相关问题和简历深挖问题，并包含完整示范回答。
- [x] 风险提示最多 3 条，具体、可解释、可行动。
- [x] 前端不展示 cover letter。
- [x] 前端不展示 evidence table。
- [x] 分析过程详情可展开查看 agent trace。
- [x] 关键 ReAct Agent 失败时，前端显示用户友好错误，后台保留具体原因。
- [x] 后端测试通过。
- [x] 前端检查和构建通过。
- [ ] 用户可上传不超过 10 MB 的文字型 PDF，解析文本可编辑且原文件不落盘。
- [ ] PDF 或粘贴纯文本中的项目、实习、教育和技能标题能被正确结构化。
