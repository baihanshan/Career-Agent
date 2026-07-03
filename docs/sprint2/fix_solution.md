# Sprint 2 输出质量问题根因与优化方案

## 1. 文档目的

本文基于 `docs/sprint2/fix_problem.md`、当前 LangGraph 工作流和实际代码实现，分析 Sprint 2 输出质量问题的根本原因，并提出可实施的架构与代码优化方案。

本文采用以下总体方案：

```text
真实 LLM ReAct Agent
+ Pydantic Structured Output
+ 证据白名单
+ 内部 ID 隔离与清洗
+ 数字声明校验
+ 最终质量门禁
```

目标不是单纯增加 Prompt，而是建立一条同时具备语义理解、证据约束、质量控制和可测试性的生成链路。

## 2. 当前架构事实

### 2.1 当前主流程

当前系统由 LangGraph 固定编排以下节点：

```text
parse_inputs
→ index_profile
→ jd_analyst
→ resume_evidence_agent
→ match_strategist
→ resume_bullet_agent
→ interview_prep_agent
→ risk_auditor_agent
→ finalize_response
```

主流程定义在：

- `backend/app/workflow/graph.py`
- `backend/app/workflow/nodes.py`

固定主流程本身是合理的。它可以保证节点顺序、错误路由、状态传递和失败处理稳定，不需要改造成完全自主的顶层 Agent。

### 2.2 当前只有部分节点真正调用 LLM

当前实际调用 LLM 的主要模块是：

- JD Analyst：提取结构化 JD 要求。
- Resume Bullet：生成匹配摘要和简历要点。
- Grounding Evaluator：尝试对生成内容进行语义评估。

虽然 Resume Evidence、Interview Prep 和 Risk Auditor 文件中定义了 `create_react_agent(...)`，但主流程实际调用的是各自类中的 `.run()` 方法。这些 `.run()` 使用固定 Python 循环、固定模板和本地工具函数，没有让 LLM 根据观察结果自主选择下一步工具。

因此当前实际架构是：

```text
LangGraph 固定流程
+ 少量 LLM 生成节点
+ Python 规则型 Agent
```

而不是设计文档中预期的：

```text
LangGraph 固定流程
+ 局部 LLM ReAct Agent
```

### 2.3 当前 ReAct 工具只返回摘要字符串

`backend/app/workflow/agent_tools.py` 中的工具主要返回 `AgentToolResult`，其中观察结果是用于 trace 展示的摘要字符串，例如“找到几个证据”“某项要求是否覆盖”。

这些返回值适合记录运行过程，但不适合作为 LLM ReAct Agent 的主要工作数据。真实 ReAct Agent 需要读取结构化的要求、完整但受控的经历摘要、证据来源、支持关系和评分，才能进行可靠语义推理。

## 3. 问题根本原因分析

## 3.1 内部 Evidence ID 泄露

### 直接原因

Resume Bullet Prompt 要求每项用户经历声明引用 `evidence_ids`，但没有建立明确的“内部字段”和“用户可见文本”边界。LLM 可能把结构化字段重新写进 `text`、答案或风险说明中。

当前 Pydantic schema 只验证字段存在和类型，例如：

```text
ResumeBullet.text: str
ResumeBullet.evidence_ids: list[str]
```

它不会检查 `text` 内是否又包含：

```text
(evidence_ids: [...])
req_3
ev_2
chunk_4
```

### 深层原因

- 内部证据引用与用户展示 DTO 使用同一个模型。
- Prompt 约束没有对应的确定性输出校验。
- Writer 只校验 `evidence_ids` 是否存在于上下文，没有检查自然语言字段是否泄露内部 ID。
- Risk Auditor 的清洗逻辑只覆盖部分风险字段，没有形成全局公共输出策略。
- 空 ID、错误 ID 和 ID 文本泄露没有统一质量门禁。

### 根本结论

该问题不是单一前端展示错误，而是领域模型缺少“内部可追踪数据”和“公开可展示数据”的边界。

## 3.2 JD 相关问题过于低级

### 直接原因

当前 Interview Prep 的 JD 问题由固定模板生成：

```text
请结合你的经历，说明你如何满足岗位对{requirement.text}的要求？
```

无论 requirement 是学历、编程基础、算法、系统设计还是多模态业务，都会套用同一个句式。

### 深层原因

- Interview Prep Agent 当前没有使用 LLM 进行问题设计。
- `JDRequirement` 只有 category、text、importance 和 keywords，没有“是否值得面试提问”“应采用何种提问方式”等信息。
- qualification、静态学历和可从简历直接确认的信息没有被过滤。
- hard skill 没有进一步拆分成基础核验、技术深挖、编码实践、系统设计或场景分析。
- Agent 没有岗位业务背景、技术约束和考察目标等问题设计上下文。
- 当前质量检查只验证问题非空、数量正确和不展示 evidence ID，不验证问题专业性。

### 根本结论

当前系统把“JD 要求”直接当成“面试问题”，缺少从岗位要求到面试能力维度、再到专业场景问题的转换层。

## 3.3 简历深挖问题复制整段项目内容

### 直接原因

当前问题模板直接拼接：

```text
请深入介绍该项目中的个人职责、技术难点、结果和复盘：{evidence.snippet}
```

答案同样直接拼接 `evidence.snippet`。

### 深层原因

- 当前项目和实习 chunk 保留整个 section，再按 800 个字符机械切分。
- 一份“项目经历”section 中可能包含多个项目，但 metadata 通常只能提取一个 project name。
- `EvidenceItem` 只有 snippet，没有结构化的项目目标、个人贡献、技术栈、难点和结果字段。
- Agent 缺少“经历摘要工具”，只能使用原始 chunk 定位项目。
- 问题生成采用固定模板，没有根据经历中的技术要素选择不同考察角度。
- 当前答案模板也直接引用 snippet，没有摘要、重组和口语化步骤。

### 根本结论

问题不只是 Prompt 写得差。更底层的原因是检索单元过粗、项目结构信息不足，导致生成模块只能消费大段原文。

## 3.4 面试答案缺少概括、针对性和扩展能力

### 直接原因

当前 `_sample_answer` 使用固定模板：

```text
在我的项目/实习经历中，{evidence.snippet}……
```

因此答案天然会复制大段简历原文。

### 深层原因

- Answer 不是由 LLM 根据问题单独生成。
- 问题和答案没有分成“问题意图”“相关事实”“回答结构”“最终回答”四个阶段。
- 没有要求先直接回答问题，再选择事实作为证据。
- 没有区分 JD 场景题与简历行为题的回答结构。
- 没有检测答案与原始 snippet 的重合比例。
- 没有检测同一经历在多个答案中的重复程度。

### 根本结论

答案生成缺少基于问题的语义规划，当前只是把证据文本包装成固定句式。

## 3.5 风险判断机械，无法理解能力证明关系

### 直接原因

当前 Risk Auditor 的主要判断规则是：

- 高优先级 requirement 是否存在 project/internship evidence。
- requirement 是否被生成的三条 resume bullet 覆盖。
- 生成内容中的数字是否原样出现在引用 snippet 中。

### 深层原因

#### 1. 覆盖判断把“项目直接命中”当作唯一有效证明

基础编程能力可以由多个项目的技术栈和实现工作共同证明，但当前风险判断偏向要求每个 requirement 都有直接的 project/internship evidence。

技能列表、教育背景、多个项目的累计证据和间接能力证明没有被正确建模。

#### 2. Requirement 与 Evidence 之间缺少语义支持类型

当前证据只有相似度 score，没有说明：

- direct support：经历直接证明该要求。
- indirect support：经历通过技术栈或任务间接证明该要求。
- contextual support：教育或技能信息提供背景支持。
- contradiction：简历与要求存在明显冲突。
- insufficient：相关但证明力度不足。

因此系统无法表达“多个 Python 项目足以间接证明编程基础”或“多模态实习直接证明了解多模态领域”。

#### 3. 检索结果没有最低相关性与语义复核

Resume Evidence Agent 将任意非 skill evidence 视为可用证据，education 和 other 也可能提前结束检索。检索后只按 section 类型和向量分数排序，没有用 LLM 判断证据是否真正支持 requirement。

#### 4. 风险候选主要由固定规则生成

Risk Auditor 没有让 LLM 对 requirement、项目语义、技术栈和任务内容进行联合推理。即使前序 Grounding Evaluator 调用了 LLM，最终风险候选仍主要由固定规则决定。

#### 5. Coverage 依赖三条简历要点而不是完整简历能力

当前 coverage gap 会把没有出现在三条生成 bullet 的高优先级 requirement 判为缺口。但三条 bullet 不可能覆盖所有 JD 要求，“没有进入最终三条 bullet”不等于“简历没有相关证据”。

### 根本结论

当前风险系统混淆了三个不同概念：

```text
简历是否具备相关证据
≠ 证据是否足够有力
≠ 该要求是否被选入三条简历要点
```

这三个判断必须拆开。

## 3.6 “数字 4 没有出现在证据中”的错误风险

### 直接原因

当前数字检查使用通用正则从生成文本中提取所有数字，再检查数字是否原样出现在证据 snippet 中。

该逻辑无法区分：

- 成果指标。
- 日期和时间区间。
- 列表编号。
- 模型版本，例如 DeepLabV3+。
- 数据集规模。
- 类别数量。
- requirement 或 evidence 文本中残留的编号。

### 深层原因

- 数字没有被建模为带类型的 claim。
- 校验器不知道数字在句子中的语义角色。
- 检查只做字符串集合差集，不做上下文对齐。
- LLM 语义评估和规则数字评估的结果直接合并，缺少冲突消解与去重。

### 根本结论

数字 grounding 的正确对象应该是“量化声明”，而不是文本中出现的所有数字。

## 3.7 当前 create_react_agent 没有真正接入运行链路

### 直接原因

三个模块都定义了 `create_*_react_agent(...)`，但 `nodes.py` 实际实例化并调用的是：

```text
ResumeEvidenceAgent().run(...)
InterviewPrepAgent().run(...)
RiskAuditorAgent().run(...)
```

### 深层原因

- 当前自定义 `LLMService` 不是 LangChain/LangGraph `BaseChatModel` 接口，不能直接作为支持工具调用的 ReAct model。
- 当前工具返回 trace 摘要字符串，而不是 Agent 可消费的结构化数据。
- Agent final output 没有独立 structured response schema。
- ReAct 工厂只在单元测试中验证创建行为，没有 workflow 集成测试证明真实工具调用发生。

### 根本结论

这是设计与运行实现未对齐的问题。仅修改 Prompt 无法解决，必须接入兼容工具调用的 ChatModel、结构化工具和 final output 解析。

## 4. 方案选择

采用方案 2：

```text
LLM ReAct Agent + 确定性安全校验
```

不采用纯 Prompt 修补，因为 Prompt 无法可靠保证 ID 不泄露、证据不越界、数字不误判和输出结构稳定。

不采用完全自主 Agent，因为当前产品需要稳定数量、固定输出结构、可解释证据和可重复测试。

## 5. 目标架构

## 5.1 顶层 LangGraph 保持固定编排

顶层仍保留确定性流程：

```text
输入解析
→ 简历结构化与索引
→ JD 结构化分析
→ Resume Evidence ReAct Agent
→ Match Strategist
→ Resume Bullet 生成与校验
→ Interview Prep ReAct Agent
→ Grounding Evaluation
→ Risk Auditor ReAct Agent
→ Public Output Gate
→ Final Response
```

固定流程负责：

- 节点执行顺序。
- shared state。
- 错误路由。
- 最大重试次数。
- 服务注入。
- 最终结果组装。
- 资源清理。

ReAct 只在需要语义判断和多轮工具调用的局部节点内部使用。

## 5.2 三层职责边界

### LLM ReAct 层

负责：

- 理解 JD 与简历语义。
- 决定调用哪些允许的工具。
- 判断证据支持关系。
- 设计专业面试问题。
- 根据问题重组答案。
- 综合多类证据生成可解释风险。

### 结构化领域层

负责：

- Pydantic 输入输出模型。
- requirement、experience、evidence、claim、risk 的明确关系。
- internal model 与 public response model 分离。
- 工具参数和返回值定义。

### 确定性质量层

负责：

- 证据 ID 白名单。
- 内部 ID 泄露检查。
- 数字声明 grounding。
- 重复问题检测。
- 问题和答案长度限制。
- 原文复制比例检测。
- 数量、枚举和必填字段校验。
- 最多三次带反馈重试。

## 6. LLM 与 ReAct 接入设计

## 6.1 增加 ReAct ChatModel 适配层

当前 `LLMService` 适合一次性 structured generation，但不提供标准工具调用消息接口。

新增独立的 `ReActModelFactory`，根据 `RunConfig` 创建兼容 LangGraph `create_react_agent` 的 ChatModel：

- OpenAI：使用支持 tool calling 的 OpenAI ChatModel。
- DeepSeek：通过 OpenAI-compatible base URL 使用支持 tool calling 的 ChatModel。
- 其他 OpenAI-compatible provider：要求模型端明确支持 function/tool calling。
- local deterministic 模式：使用 Fake ReAct Model，仅用于测试，不伪装成真实智能 Agent。

推荐新增依赖：

```text
langchain-core
langchain-openai
```

原有 `LLMService` 继续服务 JD Analyst、Resume Bullet 和 Grounding Evaluator，避免一次性重写全部 LLM 接口。

## 6.2 每个 Agent 使用真实工具调用循环

每个 ReAct Agent 的运行方式统一为：

```text
输入 state 的受控摘要
→ LLM 选择工具
→ 工具返回结构化观察结果
→ LLM 根据观察继续调用工具或结束
→ 输出 final structured result
→ 质量门禁
→ 通过或携带失败反馈重试
```

每个 Agent 最多三轮。这里的“一轮”应定义为一次完整 Agent invocation，而不是简单把 Python for-loop 伪装成 ReAct。

## 6.3 工具必须返回结构化数据

现有 `AgentToolResult` 保留用于 trace，但不能作为 Agent 的唯一工具返回值。

建议工具返回：

```json
{
  "data": {},
  "trace_summary": "用户可安全记录的摘要"
}
```

其中：

- `data` 提供给 Agent 推理，使用 Pydantic model。
- `trace_summary` 用于日志和前端分析过程展示。
- 原始 API key、完整 Prompt、隐藏推理和敏感数据不得进入 trace。

## 7. 结构化简历与证据模型升级

## 7.1 将 section 拆成独立 ExperienceRecord

目前一个“项目经历”section 可能包含多个项目。优化后应优先提取独立经历：

```text
ExperienceRecord
- experience_id
- experience_type: project | internship
- name
- company_name
- role_title
- date_range
- objective
- responsibilities
- technologies
- challenges
- actions
- outcomes
- metrics
- raw_source_chunk_ids
```

项目和实习的检索、问题生成和风险判断都应优先消费 `ExperienceRecord`，不再直接消费整段 section。

确定性 heading 和日期规则负责初步切分；当格式不规则时，可以增加一次受 structured output 约束的 LLM 结构化步骤，但不得改写或补造原文事实。

## 7.2 扩展 JDRequirement

建议新增：

```text
capability_tags
verification_mode
interviewability
question_focus
```

`verification_mode` 建议枚举：

```text
document_check       # 学历、毕业时间、明确资格
evidence_check       # 是否有项目或实习证据
technical_question   # 技术知识与工程实践
system_design        # 场景和系统设计
behavioral_question  # 协作、复盘和决策
```

`interviewability` 用于禁止把可直接从简历确认的静态条件机械转换为问题。

## 7.3 扩展 EvidenceItem

建议新增：

```text
experience_id
support_type
support_reason
capability_tags
matched_facts
source_span
```

`support_type` 建议枚举：

```text
direct
indirect
contextual
insufficient
contradiction
```

这样可以表达：

- 腾讯混元多模态实习直接支持多模态领域经验。
- 多个 Python 项目间接支持扎实编程基础。
- 技能列表为 Python 能力提供 contextual support。
- 只写“熟悉算法”但没有任何实践只能标为 insufficient，而不是完全缺失。

## 8. Resume Evidence ReAct Agent 优化方案

## 8.1 Agent 目标

针对每条 JD requirement，找到能够证明候选人能力的最小、最相关证据集合，并说明支持类型和理由。

## 8.2 允许工具

```text
search_resume_evidence(requirement, section_types, top_k)
get_experience(experience_id)
get_resume_section(section_type)
compare_requirement_to_evidence(requirement, evidence)
rerank_evidence(requirement, candidates)
```

工具必须返回结构化数据，而不是只有计数摘要。

## 8.3 ReAct 行为

1. 分析 requirement 的能力标签和验证方式。
2. 首轮搜索 project、internship。
3. 对基础技能和资格要求，必要时补充 skill、education。
4. 检查候选证据是否真正支持 requirement。
5. 如果证据仅词面相似但任务语义不相关，标记 insufficient 并继续搜索。
6. 合并来自多个经历的 indirect support。
7. 输出带支持类型和理由的 evidence selection。

## 8.4 输出模型

```text
EvidenceSelection
- requirement_id
- selected_evidence_ids
- support_level: strong | partial | weak | missing
- support_types
- rationale
- uncovered_aspects
```

## 8.5 质量门禁

- 所有 evidence ID 必须来自本轮工具返回白名单。
- strong/partial 必须至少包含一个证据。
- missing 不得同时包含“已直接支持”的证据。
- rationale 不得只复述 requirement。
- project/internship 优先，但不能排除 skill、education 的合理辅助作用。
- 相同 chunk 不重复加入同一 requirement。

## 9. Interview Prep ReAct Agent 优化方案

## 9.1 分为两个独立子任务

```text
JD Technical Interview
Resume Deep Dive Interview
```

两者共享 Agent 基础设施，但使用不同 Prompt、工具视图和质量规则。

## 9.2 JD 相关问题生成

### 问题选择规则

- `document_check` requirement 不生成面试题。
- 基础技能不能直接改写成“你如何满足”。
- technical question 应包含明确考察点。
- system design question 应包含业务目标、输入输出、约束或权衡。
- 多个相近 requirement 合并成一个更有深度的问题。

### 示例转换

输入 requirement：

```text
熟悉 Python/C++/Java 和常用算法与数据结构。
```

不生成：

```text
你如何满足熟悉 Python/C++/Java 的要求？
```

应生成类似：

```text
如果需要为高并发多模态数据处理服务设计任务队列和缓存结构，你会如何选择核心数据结构、并发模型与语言实现？请说明时间复杂度、内存开销和故障恢复方面的权衡。
```

### 输出字段

```text
question
question_type
competencies_tested
target_requirement_ids
answer_plan
sample_answer
supporting_evidence_ids
```

## 9.3 简历深挖问题生成

### 经历定位

问题只能使用：

- 项目名称。
- 公司与岗位。
- 不超过一句话的经历摘要。

不得在问题中拼接完整 snippet。

### 专业问题角度

Agent 应根据 ExperienceRecord 动态选择：

- 技术选型与替代方案。
- 数据与模型设计。
- 系统架构与性能。
- 实验设计与指标。
- 失败、困难和定位过程。
- 个人贡献与团队协作。
- 结果可信度与复盘。
- 向目标岗位场景迁移的方法。

同一经历生成多题时，每题必须有不同 focus。

## 9.4 答案生成策略

答案先生成结构化 answer plan：

```text
direct_answer
selected_facts
reasoning_or_tradeoffs
result
reflection_or_transfer
```

再由 LLM 将计划组织为自然回答。

JD 场景题的答案应遵循：

```text
问题理解
→ 方案拆解
→ 技术选择与权衡
→ 如何验证
→ 使用相关经历说明可行性
```

简历深挖答案应遵循：

```text
背景与目标
→ 个人职责
→ 关键行动与决策
→ 结果
→ 复盘
```

不得先复制 snippet 再追加模板总结。

## 9.5 Interview 质量门禁

- 不允许出现“你如何满足岗位对……的要求”式机械复述。
- qualification/document_check 不生成问题。
- 问题不得包含超过限定长度的简历原文。
- 问题必须包含 question type 和 competencies tested。
- 答案必须直接响应问题。
- supporting evidence ID 必须来自白名单。
- 用户可见字段不得出现内部 ID。
- 问题之间不得语义重复。
- 同一经历的问题 focus 不得相同。
- 答案与任一原始 snippet 的连续复制比例不得超过阈值。
- 答案中的事实、雇主、日期、技术和成果必须受证据支持。

## 10. Risk Auditor ReAct Agent 优化方案

## 10.1 拆分三个判断对象

Risk Auditor 必须分别判断：

```text
resume_coverage       # 完整简历是否存在相关证据
evidence_strength     # 证据是否足以证明要求
bullet_coverage       # 三条生成要点是否选择覆盖该要求
```

只有前两项不足时，才应考虑生成“JD 未覆盖”或“证据不足”风险。

`bullet_coverage` 不足只代表当前三条 bullet 的选择策略，不应自动被描述为候选人缺少能力。

## 10.2 允许工具

```text
get_requirement(requirement_id)
get_requirement_evidence(requirement_id)
inspect_experience(experience_id)
compare_capability_semantics(requirement, evidence_set)
check_public_claim_grounding(claim)
classify_numeric_claim(claim)
get_resume_bullet_coverage()
rank_candidate_risks(risks)
```

## 10.3 语义覆盖判断

Agent 需要综合：

- 项目与实习任务。
- 技术栈。
- 个人贡献。
- 教育背景。
- 技能列表。
- 多个经历的累计证明。
- requirement 中的“至少一个领域”等逻辑关系。

对于包含 OR 关系的 requirement，例如“搜、推、广、NLP、多模态至少一个领域”，只要存在一个领域的可靠证据，就不能判定整体未覆盖。

## 10.4 风险输出要求

每条风险必须包含：

```text
risk_type
title
jd_requirement_summary
resume_current_state
risk_reason
recommendation
severity
internal_supporting_evidence_ids
```

最后一个字段仅供后端验证和 trace 使用，不进入 public response。

Risk Auditor 不得生成以下无信息价值风险：

- 简历已经明确满足的要求。
- 只因 requirement 没进入三条 bullet 而生成的能力缺失风险。
- 只复述 JD、没有指出真实缺口的风险。
- 无法解释证据关系的风险。

## 10.5 Risk 质量门禁

- 每条风险至少引用一个 requirement。
- “未覆盖”必须经过完整简历证据搜索。
- direct/indirect support 已足够时禁止输出 missing。
- 包含 OR 条件的 requirement 必须按逻辑分支判断。
- recommendation 必须与真实缺口对应。
- 风险之间按 requirement、risk type 和语义内容去重。
- public 字段不得出现内部 ID。
- 没有可靠风险时允许返回空列表，不为了凑满三条而制造风险。

## 11. 内部 ID 隔离与证据白名单

## 11.1 分离 Internal Model 与 Public Model

内部模型保留：

```text
requirement_ids
evidence_ids
chunk_ids
experience_ids
tool_call_ids
```

公开模型只包含用户可理解的内容。

建议新增：

```text
InternalGeneratedAssets
PublicGeneratedAssets
InternalInterviewPrep
PublicInterviewPrep
InternalRiskReport
PublicRiskReport
```

`finalize_response` 只能接收经过 public projection 的模型，不应直接序列化内部 workflow state。

## 11.2 证据白名单

每个 Agent invocation 保存本轮工具实际返回的 evidence ID 集合：

```text
allowed_evidence_ids
```

Agent final output 中的所有引用必须属于该集合。未知 ID、空 ID 和跨分析 ID 必须拒绝。

## 11.3 用户可见字段扫描

统一扫描：

- resume bullet text。
- match summary。
- interview question。
- sample answer。
- risk title、reason、state、recommendation。
- trace 的 public summary。

禁止模式包括：

```text
evidence_ids
requirement_ids
supporting_evidence_ids
req_*
ev_*
chunk_*
analysis_*
```

发现泄露时优先让 Agent 根据具体失败原因重试。静默清洗只作为最终兜底，且需要留下受控日志。

## 12. 数字声明 Grounding 优化

## 12.1 将数字分成语义类型

建议新增：

```text
NumericClaim
- value
- normalized_value
- claim_type
- context
- evidence_ids
```

`claim_type`：

```text
performance_metric
business_impact
dataset_size
count
date
duration
ordinal
model_or_version
other
```

## 12.2 校验规则

- performance_metric、business_impact、dataset_size 和关键 count 必须由证据支持。
- date、duration 需要与经历时间一致，但不生成“成果数字缺失”风险。
- ordinal 不参与 grounding 风险。
- DeepLabV3+、Python 3、模型版本等按上下文分类，不作为成果数字。
- 对 `17%` 与 `0.17` 等等价表达允许规范化比较。
- 风险原因必须展示完整 claim 上下文，而不是只显示孤立数字。

## 12.3 LLM 与规则协作

规则负责稳定提取数字候选；LLM 或小型分类步骤负责判断数字语义类型。确定性代码负责最终比较和白名单验证。

## 13. Public Output Quality Gate

新增统一 `PublicOutputQualityGate`，在 final response 前运行。

检查顺序：

```text
1. Pydantic schema
2. required fields 与数量
3. evidence allowlist
4. internal ID leakage
5. unsupported factual claims
6. numeric claim grounding
7. question quality
8. answer relevance
9. snippet copy ratio
10. duplicate content
11. risk consistency
```

质量门禁返回结构化失败原因：

```text
QualityIssue
- code
- field_path
- message
- retry_instruction
- severity
```

可重试问题返回 Agent，例如：

```text
QUESTION_RESTATES_REQUIREMENT
ANSWER_COPIES_SNIPPET
INTERNAL_ID_LEAK
UNKNOWN_EVIDENCE_ID
DUPLICATE_QUESTION
UNSUPPORTED_NUMERIC_CLAIM
RISK_CONTRADICTS_EVIDENCE
```

最多重试三次。三次后仍不合格，整个分析返回对应 Agent 的受控错误，不展示不合格结果。

## 14. Prompt 设计原则

Prompt 只负责告诉模型任务、角色、工具和质量目标，不承担全部安全责任。

每个 ReAct Prompt 必须包含：

- 明确任务边界。
- 可用工具及使用时机。
- 禁止编造事实。
- 内部 ID 只能放在 structured internal fields。
- 用户可见字段不得展示 ID。
- 需要基于工具观察结果继续推理。
- 失败时继续检索或复核，而不是直接输出弱结论。
- final response schema。

Prompt 中不要求输出隐藏 Chain-of-Thought。Trace 只记录工具名、受控参数摘要、受控返回摘要和最终决策摘要。

## 15. 错误处理与可观测性

每个 ReAct Agent 记录：

```text
agent_name
attempt_number
tool_name
arguments_summary
return_summary
validation_issue_codes
final_decision_summary
```

不得记录：

- API key。
- 完整 system prompt。
- 隐藏推理过程。
- 不必要的完整简历原文。
- 原始 tool call payload 中的敏感字段。

新增受控错误类型：

```text
REACT_MODEL_UNAVAILABLE
REACT_TOOL_CALL_ERROR
REACT_OUTPUT_PARSE_ERROR
REACT_QUALITY_GATE_FAILED
REACT_EVIDENCE_VIOLATION
```

如果所选模型不支持 tool calling，应在分析开始前返回明确错误，不应静默退回当前模板逻辑。

## 16. 测试与评估方案

## 16.1 单元测试

覆盖：

- 每个 Pydantic internal/public model。
- evidence allowlist。
- ID leakage detector。
- numeric claim classifier 与 comparator。
- snippet copy ratio。
- duplicate question detector。
- requirement verification mode。
- OR requirement coverage。
- risk consistency validator。

## 16.2 ReAct Agent 测试

使用 Fake ChatModel 和固定 tool-call fixture 验证：

- Agent 确实调用工具，而不是走固定模板。
- 不同观察结果触发不同下一步工具。
- Agent 只使用 allowlist 工具。
- 工具返回结构化数据。
- final output 经过 Pydantic 解析。
- 质量失败原因会反馈给下一次重试。
- 三次失败后返回受控错误。

## 16.3 回归测试样例

将 `fix_problem.md` 中的真实问题转为回归 fixture，至少包含：

- 计算机硕士/博士 qualification 不生成低价值问题。
- Python/C++/Java requirement 生成场景型专业问题。
- 多模态岗位生成平台、数据、模型、评估或系统权衡问题。
- 项目问题不复制整段简历。
- 答案不直接复制 snippet。
- 多个 Python 项目能够共同支持编程基础。
- 语义分割能够支持机器学习/计算机视觉领域要求。
- NLP 分类、RAG 能够支持 NLP 领域要求。
- 腾讯混元多模态实习能够支持多模态领域要求。
- requirement 中“至少一个领域”的 OR 逻辑正确。
- 列表编号 `4` 不生成 unsupported metric 风险。
- 所有 public output 不包含内部 ID。

## 16.4 质量评估指标

不使用完全一致字符串判断 LLM 输出，使用结构和语义标准：

```text
ID leakage rate = 0
unknown evidence reference rate = 0
duplicate question rate = 0
qualification-as-question rate = 0
unsupported numeric claim rate = 0
question snippet copy ratio < threshold
answer snippet copy ratio < threshold
false missing-risk rate 持续下降
```

同时保留人工评审维度：

- 问题专业性。
- 问题与岗位相关性。
- 答案自然度。
- 答案针对性。
- 风险准确性。
- 建议可执行性。

## 17. 推荐实施顺序

### Phase 1：公共模型与安全边界

- 拆分 internal/public model。
- 实现 evidence allowlist。
- 实现 ID leakage detector。
- 新增 PublicOutputQualityGate 骨架。

### Phase 2：结构化经历与 requirement

- 将项目和实习拆成 ExperienceRecord。
- 扩展 JDRequirement 的 verification mode 和 capability tags。
- 扩展 EvidenceItem 的 support type 和 support reason。

### Phase 3：Resume Evidence ReAct Agent

- 增加 ReAct ChatModel 适配层。
- 将检索工具改为 structured tools。
- 接入真实 `create_react_agent`。
- 增加证据语义复核和多证据合并。

### Phase 4：Interview Prep ReAct Agent

- 分开 JD technical 和 resume deep dive prompt。
- 增加问题设计和 answer plan。
- 增加问题专业性、复制比例和重复检测。

### Phase 5：Risk Auditor ReAct Agent

- 拆分 resume coverage、evidence strength 和 bullet coverage。
- 增加语义支持关系和 OR 条件判断。
- 重构数字 claim grounding。

### Phase 6：端到端质量门禁与评估

- 接入 final public projection。
- 建立真实问题回归 fixture。
- 运行全流程质量评估。
- 删除不再使用的固定模板生成路径，避免新旧实现同时存在。

## 18. 技术栈

### 现有技术栈

```text
Python 3.11+
FastAPI
Pydantic v2
LangGraph
langgraph-prebuilt
httpx
sentence-transformers
BAAI/bge-large-zh-v1.5
Chroma
pypdf
python-multipart
pytest
Next.js 15
React 19
TypeScript
```

### 建议新增或明确使用

```text
langchain-core          # ChatModel、messages、structured tools
langchain-openai        # OpenAI 与 OpenAI-compatible tool calling
Pydantic structured output
LangGraph create_react_agent
Fake ChatModel / tool-call fixtures
```

相似度、复制比例和去重第一版可以使用 Python 标准库与现有 embedding，不必立即引入额外文本相似度依赖。

## 19. 预期目标架构

```text
                   ┌──────────────────────────┐
                   │   LangGraph Orchestrator │
                   └─────────────┬────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
             ▼                   ▼                   ▼
   Resume Evidence ReAct   Interview Prep ReAct   Risk Auditor ReAct
             │                   │                   │
             └──────────────┬────┴──────────────┬────┘
                            ▼                   ▼
                 Structured Internal Models   Agent Trace
                            │
                            ▼
                 Deterministic Quality Gates
                            │
                            ▼
                    Public Model Projection
                            │
                            ▼
                       Frontend Output
```

该架构的核心原则是：

```text
LLM 决定如何理解、检索、提问、回答和评估；
确定性代码决定什么数据允许被引用、什么结果允许被展示。
```

## 20. 最终验收标准

1. Resume Evidence、Interview Prep、Risk Auditor 在实际 workflow 中均调用真实 LLM ReAct Agent。
2. 三个 Agent 均使用结构化工具和 Pydantic final output。
3. 所有 Agent 引用的 evidence ID 均来自本轮工具返回白名单。
4. Public response 中不存在 evidence、requirement、chunk 等内部 ID。
5. 学历等 document-check requirement 不生成低价值面试问题。
6. JD 问题具有明确技术场景、考察点和约束。
7. 简历问题使用项目名或简短摘要，不复制整段经历。
8. 答案针对问题重新组织，不直接拼接 evidence snippet。
9. 风险判断区分完整简历覆盖、证据强度和 bullet 覆盖。
10. 多个项目可以共同证明基础编程等通用能力。
11. NLP、计算机视觉、多模态等领域经历能够与 JD 要求建立正确语义关系。
12. OR 条件 requirement 不会因为未满足所有分支而被错误判定未覆盖。
13. 列表编号、日期和模型版本不会产生错误数字风险。
14. 三次质量重试失败时返回受控错误，不展示不合格内容。
15. 所有 `fix_problem.md` 样例都有自动化回归测试和人工质量评审记录。
