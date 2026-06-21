# Sprint 2 ReAct 与输出质量修复总进度

本文以 `docs/sprint2/fix_solution.md` 为设计输入，追踪真实 LLM ReAct Agent、证据安全、输出质量和回归评估的实施状态。

## 总体目标

- Resume Evidence、Interview Prep、Risk Auditor 全部接入真实 LLM ReAct Agent。
- 顶层继续使用固定 LangGraph 编排。
- LLM 负责语义理解、工具选择、问题设计、回答重组和风险分析。
- 确定性代码负责 schema、证据白名单、ID 隔离、数字校验和最终质量门禁。
- `fix_problem.md` 的所有问题都具备自动化回归和人工 QA 标准。

## 推荐执行顺序

1. `react-model-runtime.md`
2. `domain-models.md`
3. `experience-structure.md`
4. `requirement-semantics.md`
5. `structured-agent-tools.md`
6. `public-output-boundary.md`
7. `quality-gates.md`
8. `resume-evidence-react-agent.md`
9. `resume-bullet-safety.md`
10. `interview-prep-react-agent.md`
11. `numeric-grounding.md`
12. `risk-auditor-react-agent.md`
13. `workflow-integration.md`
14. `regression-evaluation.md`

## 模块进度

- [x] `react-model-runtime.md`：支持工具调用的 ReAct ChatModel 和测试模型。
- [x] `domain-models.md`：Experience、EvidenceSelection、NumericClaim、QualityIssue 等内部模型。
- [x] `experience-structure.md`：按单个项目/实习生成 ExperienceRecord 和检索单元。
- [x] `requirement-semantics.md`：JD verification mode、interviewability、capability tags 和 OR 逻辑。
- [x] `structured-agent-tools.md`：结构化工具、allowlist 和安全 trace。
- [x] `public-output-boundary.md`：internal/public model 分离与 ID 泄露阻断。
- [x] `quality-gates.md`：证据、重复、复制、问题、答案和风险一致性门禁。
- [x] `resume-evidence-react-agent.md`：真实 LLM ReAct 证据检索和语义支持判断。
- [x] `resume-bullet-safety.md`：简历要点证据约束和 public 输出安全。
- [x] `interview-prep-react-agent.md`：专业 JD 问题、简历深挖和自然示范回答。
- [x] `numeric-grounding.md`：按语义类型校验量化声明。
- [ ] `risk-auditor-react-agent.md`：区分简历覆盖、证据强度和 bullet 覆盖的真实 ReAct 风险分析。
- [ ] `workflow-integration.md`：三 Agent、质量重试、错误和 public gate 接入固定 workflow。
- [ ] `regression-evaluation.md`：真实问题 fixture、自动化回归、前端检查和人工 QA。

## 阶段进度

### Phase 1：运行时与模型边界

- [x] ReAct ChatModel 可用且不支持 tool calling 时快速失败。
- [x] Internal domain models 完成。
- [x] Internal/Public output 边界完成。

### Phase 2：结构化简历、JD 与工具

- [x] 每个项目和实习形成独立 ExperienceRecord。
- [x] JD requirement 具备 verification mode 和 interviewability。
- [ ] 三个 Agent 使用结构化工具和安全 trace。

### Phase 3：生成与分析 Agent

- [x] Resume Evidence 使用真实 LLM ReAct。
- [x] Resume Bullet 不泄露 ID 且证据合法。
- [x] Interview Prep 使用真实 LLM ReAct。
- [ ] Risk Auditor 使用真实 LLM ReAct。
- [x] Numeric claim grounding 完成。

### Phase 4：集成与质量验收

- [ ] PublicOutputQualityGate 接入 final response 前。
- [ ] 旧固定模板运行路径删除。
- [ ] 完整 workflow、错误处理和 cleanup 通过。
- [ ] 回归测试和人工 QA 通过。

## 最终验收

- [ ] 三个 Agent 在实际 workflow 中均产生真实 tool call。
- [ ] 三个 Agent final output 均通过 Pydantic structured output。
- [ ] Public response 内部 ID 泄露率为 0。
- [ ] Unknown evidence reference rate 为 0。
- [ ] Qualification-as-question rate 为 0。
- [ ] Duplicate question rate 为 0。
- [ ] 项目问题和答案不大段复制简历原文。
- [ ] Python、CV/ML、NLP、RAG、多模态等能力能建立正确支持关系。
- [ ] OR requirement 按任一满足分支正确判断。
- [ ] 未进入三条 bullet 不等于简历能力缺失。
- [ ] 日期、编号和模型版本不产生错误数字风险。
- [ ] 三次重试失败返回受控错误且不展示半成品。
- [ ] 后端完整测试通过。
- [ ] 前端 `npm run check` 通过。
- [ ] 前端 `npm run build` 通过。
- [ ] 人工 QA checklist 通过并记录结果。

## 当前任务

`react-model-runtime.md`、`domain-models.md`、`experience-structure.md`、`requirement-semantics.md`、`structured-agent-tools.md`、`public-output-boundary.md`、`quality-gates.md`、`resume-evidence-react-agent.md`、`resume-bullet-safety.md`、`interview-prep-react-agent.md`、`numeric-grounding.md` 已完成；下一任务为 `risk-auditor-react-agent.md`，尚未开始。
