# Sprint 2 架构改进方案

## 目标

Sprint 2 的目标是将 Career Agent 从基础版固定流程，升级为更贴近真实求职场景的多 Agent 分析系统。重点改进两部分：

- 使用真实 embedding 和 Chroma 提升简历/JD 检索质量。
- 使用 LangGraph 多 Agent 架构，让关键环节具备局部 ReAct 多轮工具调用能力。

本方案优先保证输出质量。如果关键 ReAct Agent 失败，系统应返回分析失败，而不是降级返回低质量结果。

## 前一版本问题与改进目标

本节补充基础版已发现的问题，并说明 Sprint 2 架构需要解决的具体方向。

### 1. 简历要点问题

基础版问题：

- 网页展示中的简历要点只摘要了实习工作的部分内容。
- 简历要点没有摘要实习对应的公司名和岗位信息。
- 简历要点没有摘要平时项目内容。
- 当前输出反而摘要了一些简历中列出的技能项。
- 相比技能列表，项目经历和实习经历对求职材料更重要，当前优先级不符合预期。

已确认改进目标：

- 简历要点优先从实习经历和项目经历中生成。
- 技能列表只作为辅助信息，用于补充项目/实习表述，不单独生成简历要点。
- 实习经历要点需要包含公司名、项目内容、成果和技术栈。
- 项目经历要点需要包含项目名称、项目目标、个人贡献、技术栈、结果或可量化影响。
- 简历要点按照和 JD 的匹配度排序，生成 3 条。

### 2. 求职信草稿问题

基础版问题：

- 当前求职信草稿只生成了几句话。
- 当前输出与预期的 cover letter 初稿不符合。
- 当前求职信草稿价值较低，用户倾向于删除该模块。

已确认改进目标：

- Sprint 2 彻底删除「求职信草稿」模块。
- 从后端结果、前端展示、测试和文案中移除 cover letter。
- 删除后将页面空间让给简历要点、面试准备、风险提示等更重要模块。

### 3. 面试准备问题

基础版问题：

- 当前面试准备问题不够贴合 JD。
- 当前问题没有清晰区分面试官基于 JD 要求可能会问的问题。
- 当前问题没有充分覆盖面试官基于简历项目或实习经历可能会问的问题。
- 当前准备建议过于模板化。
- 当前准备建议经常类似于：“这个话题可以把个人经历和目标岗位要求直接连接起来。准备一段简洁的项目 walkthrough，并明确说明能力点对应的材料证据。”
- 这种建议没有结合具体简历内容、JD 要求和对应问题生成可直接参考的回答。

已确认改进目标：

- 面试准备分成两类展示：`JD 相关问题` 和 `简历深挖问题`。
- JD 相关问题根据 JD 要求生成；如果要求较多，生成 3-4 条，否则生成 1-2 条。
- 简历深挖问题根据项目经历和实习经历生成；如果内容较多，生成 3-4 条，否则生成 1-2 条。
- 每个问题需要给出完整示范回答。
- 回答不需要展示 evidence ID，但需要引用相关经历。
- 项目经历问题重点覆盖个人职责、技术难点、结果和复盘。
- 实习经历问题重点覆盖技术、工作内容和成果。
- 面试问题需要优先覆盖 JD 的高优先级要求。

### 4. 风险提示问题

基础版问题：

- 风险提示里显示“未覆盖要求：req_1”，这个 ID 对用户不友好，也无法体现具体 JD 内容。
- 每条风险提示内容高度重复。
- 当前常见提示是：“高优先级岗位要求没有被生成的简历要点覆盖。”
- 该提示不够具体，不能说明 JD 中具体哪一部分没有被简历覆盖。
- 当前风险评估没有充分结合 JD 内容和简历内容。
- 当前风险评估没有指出简历中哪些内容表述太泛。
- 当前风险提示数量可能过多或过宽泛。

已确认改进目标：

- 风险提示最多展示 3 条。
- 3 条风险提示按严重程度和求职影响排序。
- 每条风险提示需要包含：风险标题、对应 JD 要求、简历现状、为什么有风险、建议如何补充。
- 风险类型需要区分，例如 `JD 未覆盖`、`简历表述太泛`、`证据不足`、`生成内容可能夸大`。
- 前端完全隐藏内部 requirement ID，只展示 JD 原文或简短摘要。
- “简历表述太泛”的判断应优先针对项目经历和实习经历，不以技能列表为主要判断对象。

## 总体架构

Sprint 2 采用“固定主流程 + 局部 ReAct 子 Agent”的简化多 Agent 架构。

主流程仍由 LangGraph 负责，保证整体执行顺序稳定。需要自主检索、复核或多轮工具调用的子模块，使用 LangGraph 的 `create_react_agent` 实现局部 ReAct。

```text
用户输入简历和 JD
→ Coordinator / Orchestrator
→ JD Analyst Agent
→ Resume Evidence ReAct Agent
→ Match Strategist Agent
→ Resume Bullet Agent
→ Interview Prep ReAct Agent
→ Risk Auditor ReAct Agent
→ Final Response
```

其中：

- Coordinator / Orchestrator 不做 ReAct，只负责固定编排。
- Resume Evidence Agent 使用 ReAct。
- Interview Prep Agent 使用轻量 ReAct。
- Risk Auditor Agent 使用 ReAct。
- JD Analyst Agent、Match Strategist Agent、Resume Bullet Agent 不使用 ReAct。

所有 ReAct 子 Agent 最大迭代轮数统一为 3 轮。

### 架构对齐要求

总体架构需要直接解决前一版本暴露的问题，因此各 Agent 的职责边界需要满足以下要求：

- Resume Evidence ReAct Agent 必须优先检索 project 和 internship section，技能列表只作为辅助证据。
- Match Strategist Agent 必须按 JD 匹配度对项目/实习证据排序，确保后续简历要点优先使用高价值经历。
- Resume Bullet Agent 只能基于高质量项目/实习证据生成 3 条简历要点，不从技能列表单独生成要点。
- Sprint 2 的 final response 不再包含面向前端展示的 cover letter。
- Resume Bullet Agent、Interview Prep Agent、Risk Auditor Agent 是 Sprint 2 的主要生成模块。
- Interview Prep Agent 使用轻量 ReAct，必须调用高优先级 JD 要求和匹配项目/实习证据。
- Interview Prep Agent 的输出不应是模板化建议，而应是结合 JD、问题和相关经历的完整示范回答。
- Risk Auditor Agent 使用 ReAct，必须对照 JD 要求、项目/实习证据和生成内容进行复核。
- Risk Auditor Agent 必须输出具体、可解释、可行动的 top 3 风险，不展示内部 requirement ID。

## Embedding 与检索方案

### Embedding 模型

Sprint 2 使用本地开源 embedding 模型：

```text
BAAI/bge-large-zh-v1.5
```

运行方式：

- 使用 `sentence-transformers` 在本机加载模型。
- 默认本地运行，不需要用户提供 embedding API key。
- 首次运行需要下载模型。
- 优先使用本机可用的 MPS/GPU；不可用时 fallback 到 CPU。
- Sprint 2 不做 embedding 服务化部署。

模型默认缓存目录：

```text
/Users/baihanshan/Desktop/bge-models
```

### Vector Store

Sprint 2 使用 Chroma 作为本地持久化向量库。

Chroma 默认持久化目录：

```text
/Users/baihanshan/Desktop/career-agent-chroma
```

每次分析创建独立 collection：

```text
analysis_<uuid>
```

分析完成后自动删除该 collection，避免不同简历/JD 之间互相污染，也减少本地隐私数据残留。

### 结构化 Chunk

检索前不应只做普通文本 chunk，而应先做结构化简历切分。每个 chunk 需要带 section 类型和关键 metadata。

建议 section 类型：

```text
internship
project
skill
education
other
```

建议 metadata：

```text
section_type
source_name
section_title
company_name
role_title
project_name
technologies
start_char
end_char
```

结构化 chunk 的目的：

- 让 Resume Evidence Agent 优先检索项目和实习。
- 技能列表只作为辅助证据，不作为简历要点主来源。
- 风险提示能指出具体 JD 缺口和简历现状。
- 简历要点能包含公司名、项目名、技术栈、成果等关键信息。

## Agent 分工

### 1. Coordinator / Orchestrator

职责：

- 使用 LangGraph 固定主流程编排各 Agent。
- 维护 shared state。
- 将每个 Agent 的输出传递给后续 Agent。
- 收集 Agent trace。
- 处理失败状态。
- 最终组装前端展示结果。

是否使用 ReAct：

```text
不使用 ReAct。
```

原因：

- Sprint 2 需要稳定输出，不需要全局自由调度。
- 如果 Coordinator 也做 ReAct，系统复杂度和不可控性会显著上升。
- 主流程固定，局部 Agent 自主，是当前更合适的折中。

### 2. JD Analyst Agent

职责：

- 解析 JD。
- 抽取岗位要求。
- 区分 hard skill、soft skill、responsibility、qualification、nice to have。
- 判断每条要求的重要性。
- 输出结构化 JD requirements。

是否使用 ReAct：

```text
不使用 ReAct。
```

原因：

- JD 分析主要是信息抽取任务。
- 输入只有 JD，工具调用需求较少。
- 一次结构化输出更稳定。

### 3. Resume Evidence ReAct Agent

职责：

- 基于 JD requirements 检索简历证据。
- 优先检索项目经历和实习经历。
- 技能列表只作为辅助证据。
- 当初次检索只找到技能列表时，继续检索项目/实习。
- 当某个 requirement 没有证据时，尝试换 query 或使用同义表达再次检索。
- 输出经过排序的 evidence items。

是否使用 ReAct：

```text
使用 ReAct。
```

原因：

- 当前基础版容易只检索到技能列表，而不是项目和实习。
- Evidence Agent 需要根据检索结果动态决定是否继续搜索。
- 多轮工具调用能显著提升证据质量。

可用工具：

```text
search_resume_evidence(query, section_filter, top_k)
get_resume_section(section_type)
rerank_evidence(requirement, evidence_items)
```

工具说明：

- `search_resume_evidence`：向 Chroma 检索简历证据。
- `get_resume_section`：读取结构化简历 section，例如 project、internship、skill、education。
- `rerank_evidence`：按项目/实习优先、JD 匹配度和证据质量重排。

最大 ReAct 轮数：

```text
3
```

失败策略：

- 如果 3 轮内无法得到可用证据，分析失败。
- 前端展示用户友好提示。
- 后台日志记录具体失败 Agent 和原因。

### 4. Match Strategist Agent

职责：

- 根据 JD requirements 和 evidence items 判断匹配关系。
- 输出 strong、partial、weak、missing 等匹配等级。
- 判断哪些项目/实习证据最值得用于简历要点。
- 生成后续 Resume Bullet Agent 和 Interview Prep Agent 可用的匹配策略。

是否使用 ReAct：

```text
不使用 ReAct。
```

原因：

- 它主要做评分、排序和策略判断。
- 如果 Resume Evidence Agent 已经检索到高质量证据，不需要额外多轮工具调用。
- 可采用 deterministic scoring + LLM rerank 的混合方式。

### 5. Resume Bullet Agent

职责：

- 根据匹配策略生成 3 条简历要点。
- 按 JD 匹配度排序。
- 优先从项目经历和实习经历中生成。
- 不从技能列表单独生成简历要点。
- 实习经历要点需要包含公司名、项目内容、成果和技术栈。
- 项目经历要点需要包含项目名称、项目目标、个人贡献、技术栈、结果或可量化影响。
- 每条简历要点内部保留 evidence 引用，用于 grounding 和风险评估。

是否使用 ReAct：

```text
不使用 ReAct。
```

原因：

- Resume Bullet Agent 是受约束生成任务。
- 它应基于前面 Agent 提供的证据和策略生成，不应自行扩大检索范围。
- 不使用 ReAct 可以降低幻觉风险。

### 6. Interview Prep ReAct Agent

职责：

- 生成两类面试问题：
  - JD 相关问题。
  - 简历深挖问题。
- JD 相关问题优先根据高优先级 JD requirements 生成。
- 简历深挖问题根据项目经历和实习经历生成。
- 每个问题给出完整示范回答。
- 回答应结合简历内容、JD 要求和问题本身。
- 回答中不展示 evidence ID，但需要引用相关经历。

生成数量：

- 如果 JD 要求较多，JD 相关问题生成 3-4 条；否则生成 1-2 条。
- 如果项目/实习经历较多，简历深挖问题生成 3-4 条；否则生成 1-2 条。

是否使用 ReAct：

```text
使用轻量 ReAct。
```

原因：

- Interview Prep Agent 需要同时参考 JD 高优先级要求和简历项目/实习经历。
- 轻量 ReAct 可以帮助它先定位关键要求和关键经历，再生成问题与回答。
- 但为了控制复杂度，最大轮数限制为 3。

可用工具：

```text
get_high_priority_jd_requirements()
get_matched_project_and_internship_evidence()
draft_answer(question, evidence, jd_requirement)
```

工具说明：

- `get_high_priority_jd_requirements`：获取高优先级 JD 要求。
- `get_matched_project_and_internship_evidence`：获取匹配度最高的项目/实习经历。
- `draft_answer`：根据问题、经历和 JD 要求生成完整示范回答。

最大 ReAct 轮数：

```text
3
```

失败策略：

- 如果 3 轮内无法生成合格问题和回答，分析失败。
- 前端展示用户友好提示。
- 后台日志记录具体失败 Agent 和原因。

### 7. Risk Auditor ReAct Agent

职责：

- 对 JD requirements、简历证据和生成内容做最终风险评估。
- 只输出最重要的 3 条风险。
- 风险按严重程度和求职影响排序。
- 不展示 `req_1` 这类内部 ID。
- 每条风险需要包含：
  - 风险标题。
  - 对应 JD 要求。
  - 简历现状。
  - 为什么有风险。
  - 建议如何补充。

风险类型：

```text
JD 未覆盖
简历表述太泛
证据不足
生成内容可能夸大
```

是否使用 ReAct：

```text
使用 ReAct。
```

原因：

- 风险评估需要反复对照 JD 和简历证据。
- 单次生成容易出现泛泛提示。
- ReAct 可以针对高优先级 JD 要求逐条检查证据覆盖。
- 如果证据只是技能列表，应继续检查项目和实习。
- 最终只保留最重要的 3 条具体风险。

可用工具：

```text
check_requirement_coverage(requirement)
find_resume_vague_claims()
check_generated_claim_grounding(claim)
rank_top_risks(risks, limit=3)
```

工具说明：

- `check_requirement_coverage`：检查某条 JD 是否被简历项目/实习覆盖。
- `find_resume_vague_claims`：找项目/实习中表述太泛的内容。
- `check_generated_claim_grounding`：检查生成内容是否被证据支撑。
- `rank_top_risks`：只保留最重要 3 条风险。

最大 ReAct 轮数：

```text
3
```

失败策略：

- 如果 3 轮内无法生成具体、可解释的风险提示，分析失败。
- 前端展示用户友好提示。
- 后台日志记录具体失败 Agent 和原因。

## Shared State

各 Agent 通过 LangGraph shared state 传递数据。

建议 state 包含：

```text
analysis_id
profile_documents
structured_resume_sections
profile_chunks
chroma_collection_name
jd_requirements
retrieved_evidence
match_strategy
resume_bullets
interview_prep
risk_report
agent_traces
errors
warnings
```

其中：

- `retrieved_evidence` 内部保留，但前端不展示完整证据表。
- `agent_traces` 默认不直接展示，进入“分析过程详情”模块。
- `errors` 面向前端时转换为用户友好提示。
- 后台日志保留具体 Agent 失败原因。

## 前端展示模块

Sprint 2 删除求职信草稿和证据表展示。

最终页面模块：

```text
1. 匹配摘要
2. 简历要点
3. 面试准备
   - JD 相关问题
   - 简历深挖问题
4. 风险提示
5. 分析过程详情（可展开）
```

说明：

- 求职信草稿从产品功能中彻底移除。
- 证据表不在前端展示。
- evidence 引用仍在后端内部保留，用于 grounding、风险评估和 debug trace。
- 分析过程详情默认折叠，用户需要时可展开查看 Agent trace。

## Agent Trace

ReAct Agent 的工具调用轨迹需要记录，但默认不直接展示。

前端展示方式：

```text
分析过程详情（可展开）
```

可包含内容：

```text
Agent 名称
工具调用名称
查询参数摘要
工具返回结果摘要
最终决策摘要
```

不应默认暴露过多内部提示词或完整模型思考内容。展示重点是让用户理解系统如何检索和判断，而不是展示所有隐藏推理。

## 错误处理

Sprint 2 采用质量优先策略。

如果关键 ReAct 子 Agent 失败：

- 整个分析失败。
- 前端展示用户友好提示。
- 后台日志记录具体失败 Agent、失败工具、失败原因和 trace。

前端不直接展示技术性错误，例如：

```text
Resume Evidence Agent failed after 3 iterations
```

前端应展示类似：

```text
分析失败：系统未能从简历中找到足够可靠的项目或实习证据，请补充更具体的经历后重试。
```

后台日志可记录完整原因。

## 关键设计原则

1. 项目和实习优先于技能列表。
2. 真实 embedding 和 Chroma 用于提升证据检索质量。
3. 主流程固定，局部 Agent 自主。
4. ReAct 只用于最需要多轮工具调用的 Agent。
5. 所有 ReAct Agent 最大 3 轮。
6. 质量优先，关键 Agent 失败时不降级返回低质量结果。
7. 前端展示结果应面向用户，不展示内部 requirement ID。
8. 内部 evidence 引用必须保留，用于 grounding 和风险评估。
9. 风险提示最多 3 条，并且必须具体、可解释、可行动。
10. Agent trace 默认隐藏，可展开查看。
