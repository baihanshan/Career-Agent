# 交接记录

## 当前上下文

更新日期：2026-07-04

### 当前目标

- 已完成：用户用真实 DeepSeek 复测 `/analysis` 已跑通，前端内容正常显示；随后修复前端 agent trace 列表重复 React key warning，并将 Risk Auditor 改为岗位类型感知的核心风险优先逻辑，避免泛软技能风险压过真实筛选风险。真实复测又触发 `REACT_EVIDENCE_VIOLATION` 和 `REACT_OUTPUT_PARSE_ERROR`，已补 Risk Auditor 内部 evidence id 规范化、最终风险 JSON 容错解析，以及 Interview Prep 内部 question evidence/requirement id 反推规范化。2026-07-02：按用户要求调整 JD 相关面试问题生成，使其侧重岗位能力考察型问题，而不是默认围绕简历项目追问。2026-07-04：在收敛版 provider 范围内新增模型名自动获取：仅保留 OpenAI、DeepSeek、兼容接口、本地演示，后端新增 `POST /models/list`，前端模型输入支持下拉选择和手动输入。

### 当前项目状态

- 生产代码已无 `create_react_agent` / `langgraph.prebuilt` 引用；依赖改为显式 `langchain>=1.0.0`，移除直接 `langgraph-prebuilt` 依赖。OpenAI provider 保留 Pydantic `response_format`，DeepSeek/openai-compatible provider 改走 JSON prompt + fallback parser。三个 ReAct agent 共享 `parse_json_payload_from_text`，可解析纯 JSON、fenced JSON、自然语言前缀后的 JSON。`interview_prep_agent` 会把内部 `supporting_evidence_ids` 规范化为本轮工具 allowlist 中的真实 evidence id；若真实模型漏填/错填 question 的 target requirement，则会从本轮 allowed evidence 反推 requirement，避免内部追踪字段导致 `REACT_EVIDENCE_VIOLATION`。`InterviewPrepAgent` prompt/payload 已明确区分 `jd_questions` 与 `resume_deep_dive_questions`：JD 问题偏岗位能力考察，简历深挖问题负责项目/实习/经历追问；质量门禁会阻止 JD 问题点名具体简历经历。Risk Auditor prompt/payload 已加入 `risk_audit_policy`，先判断岗位类型，再按技术研发或产品/项目管理核心风险维度排序，软技能默认降权；Risk Auditor 也会在质量门禁前把 `internal_supporting_evidence_ids` 规范化为本轮工具 allowlist 中的真实 evidence id，并兼容 `risk_report.risks`、裸 risks 数组、中文 severity、字符串 priority 和字符串 id。前端 `AgentTraceDetails` 的 trace 与 step key 已加入 index，避免相同 tool/arguments summary 产生重复 key warning。前端模型服务只保留 OpenAI、DeepSeek、兼容接口和本地演示；`POST /models/list` 代理远程 provider `/models`，返回 `{models, warning}`，失败时不回显 API key 且不阻断手动输入；`LlmSettings` 的模型框使用原生 `datalist` 实现下拉选择 + 手动输入。完整后端测试在 `RETRIEVAL_BACKEND=fake` 下通过，前端 `npm run check` / `npm run build` 通过；build 仅有既有 Next SWC 本地包加载 warning。

### 最近变更

- 2026-07-04：按用户要求实现模型名自动识别，但不恢复多供应商 preset。新增 `backend/app/llm/model_catalog.py`、`ModelListRequest/ModelListResponse`、`POST /models/list`；DeepSeek/OpenAI 使用默认 `/models` 地址，兼容接口根据 Base URL 拼 `/models`。前端 `LlmSettings` 模型输入改为可手动输入且可通过 `datalist` 下拉选择，新增「获取模型列表」按钮和受控中文提示。验证：`backend/tests/test_model_catalog.py backend/tests/test_api.py`、完整后端 pytest、`npm run check`、`npm run build` 均通过。
- 2026-07-02：调整 Interview Prep 的 JD 问题边界：`jd_questions` 必须偏岗位能力考察型问题，基于 JD 的岗位方向、核心职责、必备技能、业务/技术场景、约束和验证指标出题；项目/实习/公司/经历追问应放入 `resume_deep_dive_questions`。补充 `question_generation_policy` payload 和 `JD_QUESTION_USES_RESUME_EXPERIENCE` 质量门禁。本次按用户要求未新增测试，仅执行 `py_compile`。
- 2026-07-01：用户用日志确认失败阶段为 `agent=interview_prep_agent tool=quality_gate`，错误为 `REACT_EVIDENCE_VIOLATION`。补充回归测试和修复：当真实模型漏填/错填 JD question 的 `target_requirement_ids` 且 `supporting_evidence_ids` 不在 allowlist 时，从本轮 allowed evidence 回填 supporting evidence，并反推 interviewable requirement id。
- 2026-07-01：用户真实复测返回 `REACT_OUTPUT_PARSE_ERROR`。补充 Risk Auditor final parser 容错：支持模型返回 `{"risk_report":{"risks":[...]}}`、直接返回 risks 数组，并归一化中文 severity、字符串 priority、字符串 requirement/evidence id，避免 DeepSeek 在岗位类型分析后改变 JSON 包装形态导致结构化解析失败。
- 2026-07-01：用户真实复测返回 `REACT_EVIDENCE_VIOLATION` 且后端无详细日志。补充 Risk Auditor 回归测试：当模型在 `internal_supporting_evidence_ids` 中填入未知 evidence id 时，根据 risk 的 `requirement_ids` 回填同 requirement 且本轮工具已 allowlist 的真实 evidence id，避免内部追踪字段导致 public 结果被阻止。
- 2026-07-01：Risk Auditor 改为岗位类型感知风险审计：`RISK_AUDITOR_AGENT_PROMPT` 要求先判断 role type，`_invocation_prompt` 提供 `risk_audit_policy` 和 requirement 文本/标签，内部 risk 支持 `risk_dimension` / `risk_priority`，`rank_candidate_risks` 按 severity、priority、dimension 排序，软技能默认低优先级。新增回归测试覆盖 policy payload 和核心技术风险优先于泛软技能。
- 2026-07-01：真实 DeepSeek 复测已跑通；修复前端 `ResultView.tsx` 中 agent trace step 使用 `tool_name + arguments_summary` 作为 key 导致重复 React key warning 的问题，并在 `frontend/scripts/verify-structure.mjs` 增加回归检查。
- 2026-07-01：用户复现日志显示 `interview_prep_agent tool=quality_gate`，前端报“生成结果引用了无效证据”。修复为：解析带自然语言前缀的 JSON；在面试准备校验前按 target requirement / experience chunks 规范化 supporting evidence id。
- 2026-06-30：用户复现日志显示三次 `GraphRecursionError: Recursion limit of 10 reached`；修复为动态递归预算 `max(max_steps * 2 + 4, requirement_count * 4 + 12, 30)`，并新增 `REACT_RECURSION_LIMIT_ERROR`。
- 2026-06-30：`ResumeEvidenceAgent` 在 `_parse_final_selections` 异常时增加脱敏 warning 日志，并补充 caplog 回归测试。
- 2026-06-30：更新 `AGENTS.md`，补充 CareerPilot Agent 仓库结构说明。
- 2026-06-30：`ResumeEvidenceAgent`、`InterviewPrepAgent`、`RiskAuditorAgent` 改用 `langchain.agents.create_agent(system_prompt=..., response_format=...)`。
- 2026-06-30：`react_response_format` 改为只对 OpenAI provider 返回 Pydantic schema；三个 Agent prompt 增加短 JSON example。

### 未解决问题

- 暂无明确未解决问题。

### 下一步建议

- 如用户复测模型列表失败，优先确认 provider、API key、Base URL 是否正确；兼容接口要求 Base URL 指向 OpenAI-compatible 根路径，例如以 `/v1` 结尾时会请求 `/v1/models`。避免贴 API key 和完整简历。

### 相关记忆条目

- `project_memory/active/decisions/ADR-0001-use-langchain-create-agent.md`
- `project_memory/active/bugs/BUG-0001-resume-evidence-recursion-limit.md`
- `project_memory/active/bugs/BUG-0002-interview-prep-evidence-id-normalization.md`
- `project_memory/active/topics/TOPIC-0001-role-aware-risk-auditor.md`
- `project_memory/active/topics/TOPIC-0002-interview-prep-question-boundary.md`
- `project_memory/active/topics/TOPIC-0003-model-list-combobox.md`

## 最近交接记录
