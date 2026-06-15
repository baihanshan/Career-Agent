# CareerPilot Agent 设计文档

日期：2026-06-11

## 项目目标

CareerPilot Agent 是一个面向求职者的 agentic LLM application。它帮助用户把真实的个人背景材料和目标岗位 JD 转化为有证据支撑的求职内容，包括岗位匹配分析、定制化简历 bullet、cover letter 草稿和面试准备建议。

这个项目的定位是一个适合放入作品集的工程项目，目标岗位是 agent developer 或 LLM application engineer。项目需要展示你在 RAG、多步骤 agent 工作流、证据支撑生成、评估、前后端集成和部署方面的实践能力。

## MVP 范围

第一版聚焦核心闭环：

1. 用户上传个人职业材料和目标岗位 JD。
2. 系统把个人材料索引成可检索的知识库。
3. Agent 从 JD 中提取结构化岗位要求。
4. Agent 从用户材料中检索相关证据。
5. Agent 生成针对该岗位的求职内容。
6. Evaluator 检查生成内容是否被检索证据支撑。

MVP 不包含自动投递、浏览器控制、多用户登录、支付、社交功能或复杂简历排版。这些功能可以等核心 agent 闭环稳定后再作为扩展加入。

## 目标用户

目标用户是正在申请技术岗位的毕业生或早期职业阶段求职者。用户可能有简历、项目描述、课程记录、GitHub 项目介绍等分散材料，但需要一个系统帮助他们根据具体 JD 定制申请材料，同时避免编造不存在的经历。

## 核心用户流程

1. 用户打开 Web 应用。
2. 用户上传或粘贴个人材料：
   - PDF 或 Markdown 简历
   - 项目经历描述
   - 课程或技能笔记
   - 可选的 GitHub 项目总结
3. 用户粘贴目标岗位 JD。
4. 后端解析并索引个人材料。
5. JD 分析 agent 提取岗位要求。
6. 匹配 agent 对比岗位要求和个人证据。
7. 写作 agent 生成：
   - 岗位匹配总结
   - 定制化简历 bullet 建议
   - Cover letter 草稿
   - 面试准备主题
8. 评估 agent 返回 grounding 和覆盖率检查。
9. 前端展示生成结果、证据引用和风险提示。

## 系统架构

MVP 分为四层：

### 前端

使用 Next.js 和 React 构建用户界面。

职责：

- 上传或粘贴用户材料。
- 粘贴目标岗位 JD。
- 触发分析流程。
- 展示 indexing、analysis、generation、evaluation 等进度状态。
- 展示带证据引用的生成结果。
- 当 evaluator 发现内容证据不足时展示警告。

### 后端 API

使用 Python 和 FastAPI。

职责：

- 接收上传文件和文本输入。
- 将文档解析为文本。
- 协调索引和 agent 执行流程。
- 提供创建分析任务和获取结果的接口。
- 使用 Pydantic 明确定义 request 和 response schema。

### 检索层

使用 Chroma 作为本地向量数据库。

职责：

- 将用户材料切分成语义上合理的片段。
- 生成 embedding。
- 存储带 metadata 的文本片段。
- 根据岗位要求和生成任务检索相关证据。

Metadata 应包含 source file、section label、chunk id，以及在可行情况下包含字符位置。

### Agent 工作流

使用 LangGraph 定义可控的状态机，而不是松散的 autonomous agent。

Graph 包含以下节点：

- `parse_inputs`：标准化用户材料和岗位 JD。
- `index_profile`：切分并 embedding 用户材料。
- `analyze_jd`：从 JD 中提取结构化岗位要求。
- `retrieve_evidence`：为每个岗位要求检索相关用户证据。
- `score_match`：估计匹配强度和技能缺口。
- `write_application`：生成简历 bullet、cover letter 和面试准备建议。
- `evaluate_grounding`：检查生成内容是否被检索证据支持。
- `finalize_response`：整理最终结果并返回给前端。

工作流在 graph 层面应保持确定性。LLM 调用只发生在具体节点内部，节点顺序和状态流转需要显式可控。

## 数据流

输入数据：

- `profile_documents`：上传文件或粘贴文本
- `job_description`：粘贴的岗位 JD
- `run_config`：模型名称、temperature、检索参数

中间状态：

- `profile_chunks`
- `jd_requirements`
- `retrieved_evidence`
- `match_analysis`
- `generated_assets`
- `evaluation_report`

输出数据：

- 岗位匹配总结
- 按岗位要求组织的证据表
- 定制化简历 bullet
- Cover letter 草稿
- 面试准备主题
- Grounding 和 hallucination 风险提示

## LLM 的职责边界

LLM 应负责语言和推理任务，而不是隐藏的控制流。

LLM 负责：

- 提取结构化岗位要求。
- 总结相关证据。
- 起草求职材料。
- 判断生成声明是否被证据支持。

非 LLM 负责：

- 文件处理
- 文本切分
- Embedding 存储
- 检索
- API 校验
- 工作流控制
- 数据持久化
- UI 状态渲染

## 证据支撑规则

生成的求职内容必须遵循以下规则：

1. 任何关于用户经历的声明，都必须能追溯到检索证据。
2. 如果证据较弱，系统应标记该声明证据较弱，而不是自信地输出。
3. 写作 agent 不应编造雇主、项目成果、指标、工具或日期。
4. Evaluator 应标记不受支持的声明，以及未覆盖的重要 JD 要求。

前端需要让 grounding 可见，例如在重要输出旁展示 source snippet 或 source label。

## 评估设计

MVP 先使用自定义 evaluator，而不是一开始依赖外部评估库。

Evaluator 检查：

- Grounding：生成声明是否被检索证据支持。
- Coverage：是否覆盖了 JD 中最重要的要求。
- Specificity：简历 bullet 是否具体，而不是泛泛而谈。
- Risk：内容中是否出现了编造的数字、雇主、工具或成果。

后续版本可以加入 Ragas 或 LangSmith evaluation，但第一版应优先保持评估逻辑可理解、可检查。

## 错误处理

预期错误和处理方式：

- 空文件或不可读文件：展示明确的上传错误。
- 不支持的文件类型：拒绝上传，并提示可接受格式。
- 用户资料过短：提示输出质量会受限。
- JD 过长：进行摘要或截断，并显示可见警告。
- 检索到的证据较弱：继续生成，但标记 weak match。
- LLM 调用失败：重试一次，仍失败则返回可恢复错误。
- 向量数据库失败：返回 indexing error，并避免继续生成。

## 测试策略

第一版应围绕最高风险行为写聚焦测试。

后端测试：

- Pydantic schema 校验。
- 文档切分。
- 岗位要求提取的输出结构。
- 检索结果是否带有 chunk metadata。
- LangGraph workflow 是否能基于 fixture 输入到达最终状态。
- Evaluator 是否能在受控样例中标记不受支持的声明。

前端测试：

- 上传和粘贴表单能够正常渲染。
- 分析结果区块能够正常渲染。
- 当 evaluator 返回风险时，警告状态能够正常显示。

集成测试：

- 使用一份小型 sample profile 和 sample JD 能生成完整分析结果。
- 生成声明包含 evidence references。

## 推荐技术栈

- Python 3.11+
- FastAPI
- Pydantic
- LangGraph
- LangChain 或 LlamaIndex 作为检索工具层
- Chroma
- OpenAI API 作为第一版模型接口
- Next.js
- React
- TypeScript
- Docker

## 里程碑

### Milestone 1：后端骨架

- 创建 FastAPI app。
- 定义 request 和 response schema。
- 添加 health check。
- 添加返回 mocked data 的 sample analysis endpoint。

### Milestone 2：文档摄取和检索

- 先支持纯文本和 Markdown。
- 文本摄取跑通后再加入 PDF parsing。
- 切分 profile material。
- 将 chunks 存入 Chroma。
- 能针对 sample query 检索 chunks。

### Milestone 3：LangGraph 工作流

- 构建 graph state。
- 添加 JD 分析节点。
- 添加检索节点。
- 添加匹配评分节点。
- 添加写作节点。
- 添加评估节点。

### Milestone 4：前端 MVP

- 构建上传和粘贴界面。
- 触发后端分析任务。
- 渲染 match analysis、resume bullets、cover letter 和 evaluation warnings。

### Milestone 5：作品集打磨

- 添加 sample data。
- 添加包含架构图和截图的 README。
- 添加 Docker 配置。
- 添加部署说明。
- 添加一篇简短技术说明，解释设计选择。

## 简历包装方式

这个项目可以先写成如下简历 bullet：

Built CareerPilot Agent, an agentic LLM application using FastAPI, LangGraph, Chroma, and React that converts user career materials and job descriptions into grounded resume bullets, cover letters, and interview plans with evidence citations and hallucination checks.

项目实现后，应根据真实结果补充可量化信息，例如 latency、evaluation case 数量、支持的文件类型或部署指标。

## 待定决策

这些决策可以在 implementation planning 阶段确定：

- 检索抽象层主要使用 LangChain 还是 LlamaIndex。
- 第一版前端使用纯 CSS、Tailwind，还是现成组件库。
- MVP 是否只在本地存储用户数据，还是加入轻量数据库。
- 默认使用哪个 OpenAI 模型来平衡成本和质量。

## 成功标准

MVP 达成以下标准即可认为成功：

- 用户可以提供个人资料和岗位 JD。
- 应用可以生成完整的岗位匹配分析。
- 生成的简历 bullet 和 cover letter 被检索证据支撑。
- 不受支持或有风险的声明会被标记。
- 架构清晰到足以在面试中讲解。
- 仓库包含测试、sample data，以及适合 recruiter 或 hiring manager 阅读的 README。
