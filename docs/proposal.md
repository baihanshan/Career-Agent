# CareerPilot Agent Proposal

## 1. 项目概述

CareerPilot Agent 是一个面向求职者的 agentic LLM application。它帮助用户把真实的个人背景材料和目标岗位 JD 转化为有证据支撑的求职内容，包括岗位匹配分析、定制化简历 bullet、cover letter 草稿和面试准备建议。

这个项目适合作为 AI 硕士背景下的实践型作品集项目。它不只是一个普通的文本生成工具，而是一个完整的 AI 应用工程项目，覆盖 RAG、多步骤 agent 工作流、证据支撑生成、评估、前后端集成和部署。完成后，项目可以作为简历中的核心项目经历，用来证明自己具备从需求分析到系统实现的 AI 编程实践能力。

## 2. 项目动机

很多求职者有真实的教育经历、课程项目、技能笔记、简历和 GitHub 项目材料，但在面对具体岗位 JD 时，很难快速判断自己与岗位的匹配度，也很难把已有经历改写成有针对性的求职内容。

与此同时，直接使用通用聊天模型生成简历或 cover letter 容易产生两个问题：

1. 生成内容泛泛而谈，不能紧贴目标岗位要求。
2. 模型可能编造不存在的项目、成果、数据、工具或经历。

CareerPilot Agent 的核心价值是：在用户真实背景材料的约束下，根据目标 JD 生成有证据引用、可检查、风险可见的求职内容。

## 3. 目标用户

MVP 的目标用户是正在申请技术岗位的毕业生或早期职业阶段求职者，尤其是有 AI、软件工程、数据科学或相关技术背景，但实践项目经历相对有限的人。

用户可能拥有以下材料：

- 简历 PDF 或 Markdown 文档
- 课程项目描述
- 技能学习笔记
- GitHub 项目介绍
- 实习、科研或课堂作业材料
- 目标岗位的 job description

系统帮助用户从这些分散材料中提取可用证据，并围绕目标岗位生成更有针对性的申请内容。

## 4. MVP 范围

第一版聚焦核心闭环，不追求复杂功能堆叠。

MVP 包含：

1. 用户上传或粘贴个人职业材料。
2. 用户粘贴目标岗位 JD。
3. 系统解析并索引个人材料。
4. Agent 从 JD 中提取结构化岗位要求。
5. Agent 从用户材料中检索相关证据。
6. Agent 生成岗位匹配分析、简历 bullet、cover letter 草稿和面试准备建议。
7. Evaluator 检查生成内容是否被检索证据支撑。
8. 前端展示生成结果、证据引用和风险提示。

MVP 暂不包含：

- 自动投递
- 浏览器控制
- 多用户登录
- 支付系统
- 社交功能
- 复杂简历排版

这些功能可以在核心 agent 闭环稳定后作为后续扩展。

## 5. 核心用户流程

1. 用户打开 Web 应用。
2. 用户上传或粘贴个人材料，例如简历、项目描述、课程笔记或 GitHub 项目总结。
3. 用户粘贴目标岗位 JD。
4. 后端将用户材料解析为文本并建立可检索知识库。
5. JD 分析 agent 提取岗位职责、硬技能、软技能、加分项和隐含要求。
6. 匹配 agent 根据岗位要求检索用户材料中的相关证据。
7. 写作 agent 生成定制化求职内容。
8. 评估 agent 检查 grounding、coverage、specificity 和 hallucination risk。
9. 前端展示最终结果，并在证据不足的地方给出清晰提示。

## 6. 系统架构

MVP 采用四层架构：前端、后端 API、检索层和 agent 工作流。

### 6.1 前端

前端使用 Next.js、React 和 TypeScript 构建。

主要职责：

- 上传或粘贴用户材料。
- 粘贴目标岗位 JD。
- 触发分析流程。
- 展示 indexing、analysis、generation、evaluation 等进度状态。
- 展示岗位匹配分析、简历 bullet、cover letter 和面试建议。
- 在生成内容旁展示 evidence source 或 source snippet。
- 当 evaluator 发现内容证据不足时展示风险警告。

### 6.2 后端 API

后端使用 Python、FastAPI 和 Pydantic。

主要职责：

- 接收上传文件和文本输入。
- 将文档解析为纯文本。
- 协调索引、检索和 agent workflow。
- 提供创建分析任务和获取结果的 API。
- 使用 Pydantic 明确定义 request 和 response schema。

### 6.3 检索层

检索层使用 Chroma 作为本地向量数据库。

主要职责：

- 将用户材料切分为语义上合理的 chunks。
- 为 chunks 生成 embeddings。
- 保存带 metadata 的文本片段。
- 根据岗位要求检索相关用户证据。

每个 chunk 的 metadata 应尽量包含：

- source file
- section label
- chunk id
- character offset

### 6.4 Agent 工作流

Agent 工作流使用 LangGraph 构建可控状态机，而不是使用松散的 autonomous agent。

核心节点包括：

- `parse_inputs`：标准化用户材料和岗位 JD。
- `index_profile`：切分并 embedding 用户材料。
- `analyze_jd`：从 JD 中提取结构化岗位要求。
- `retrieve_evidence`：为每个岗位要求检索相关用户证据。
- `score_match`：估计匹配强度和技能缺口。
- `write_application`：生成简历 bullet、cover letter 和面试准备建议。
- `evaluate_grounding`：检查生成内容是否被检索证据支持。
- `finalize_response`：整理最终结果并返回给前端。

工作流在 graph 层面保持确定性。LLM 负责语言理解、推理和写作，但不负责隐藏的系统控制流。

## 7. 数据流设计

输入数据：

- `profile_documents`：上传文件或粘贴文本
- `job_description`：目标岗位 JD
- `run_config`：模型名称、temperature、检索参数

中间状态：

- `profile_chunks`
- `jd_requirements`
- `retrieved_evidence`
- `match_analysis`
- `generated_assets`
- `evaluation_report`

最终输出：

- 岗位匹配总结
- 按岗位要求组织的证据表
- 定制化简历 bullet
- Cover letter 草稿
- 面试准备主题
- Grounding 和 hallucination 风险提示

## 8. 证据支撑规则

CareerPilot Agent 的一个核心原则是：不编造经历。

生成内容必须遵循以下规则：

1. 任何关于用户经历的声明，都必须能追溯到检索证据。
2. 如果证据较弱，系统应标记为 weak match，而不是自信输出。
3. 写作 agent 不应编造雇主、项目成果、指标、工具或日期。
4. Evaluator 应标记不受支持的声明，以及未覆盖的重要 JD 要求。
5. 前端应让 grounding 可见，使用户知道每条建议来自哪些背景材料。

这个设计可以展示项目对 LLM hallucination 风险的工程化处理，而不是只依赖 prompt 要求模型“不要编造”。

## 9. 评估设计

MVP 先实现自定义 evaluator，保持评估逻辑清晰、可检查、可测试。

Evaluator 检查四类问题：

- Grounding：生成声明是否被检索证据支持。
- Coverage：是否覆盖 JD 中最重要的要求。
- Specificity：简历 bullet 是否具体，而不是泛泛而谈。
- Risk：是否出现编造的数字、雇主、工具或成果。

后续版本可以加入 Ragas 或 LangSmith evaluation，但第一版优先保证评估流程可理解、可调试。

## 10. 错误处理

系统需要处理以下预期错误：

- 空文件或不可读文件：展示明确上传错误。
- 不支持的文件类型：拒绝上传，并提示可接受格式。
- 用户资料过短：提示输出质量会受限。
- JD 过长：进行摘要或截断，并显示可见警告。
- 检索证据较弱：继续生成，但标记 weak match。
- LLM 调用失败：重试一次，仍失败则返回可恢复错误。
- 向量数据库失败：返回 indexing error，并避免继续生成。

## 11. 技术栈

建议技术栈如下：

- Python 3.11+
- FastAPI
- Pydantic
- LangGraph
- LangChain 或 LlamaIndex
- Chroma
- OpenAI API
- Next.js
- React
- TypeScript
- Docker

这个技术栈能覆盖 AI 应用工程岗位常见能力点：API 设计、RAG、agent workflow、structured output、evaluation、前后端集成和部署。

## 12. 测试策略

第一版测试应聚焦最高风险行为。

后端测试：

- Pydantic schema 校验。
- 文档切分逻辑。
- JD requirement extraction 的输出结构。
- 检索结果是否包含 chunk metadata。
- LangGraph workflow 是否能基于 fixture 输入到达最终状态。
- Evaluator 是否能在受控样例中标记不受支持的声明。

前端测试：

- 上传和粘贴表单能够正常渲染。
- 分析结果区块能够正常渲染。
- 当 evaluator 返回风险时，警告状态能够正常显示。

集成测试：

- 使用小型 sample profile 和 sample JD 生成完整分析结果。
- 生成声明包含 evidence references。

## 13. 实施里程碑

### Milestone 1：后端骨架

- 创建 FastAPI app。
- 定义 request 和 response schema。
- 添加 health check。
- 添加返回 mocked data 的 sample analysis endpoint。

### Milestone 2：文档摄取和检索

- 先支持纯文本和 Markdown。
- 支持上传文字型 PDF，由后端提取文本并回填前端文本框。
- 扫描件 PDF 和 OCR 不进入 Sprint 2 范围。
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

### Milestone 5：部署和作品集整理

- 使用 Docker 统一本地运行环境。
- 编写 README、架构图和 demo walkthrough。
- 准备 sample profile 和 sample JD。
- 记录评估样例，展示系统如何避免 unsupported claims。

## 14. 简历价值

完成该项目后，可以在简历中将其描述为一个 evidence-grounded career application agent。项目亮点包括：

- 使用 LangGraph 构建多步骤 agent workflow。
- 使用 RAG 将个人背景材料转化为可检索证据库。
- 通过 evaluator 检查生成内容是否被证据支撑。
- 使用 FastAPI 和 Pydantic 构建结构化后端服务。
- 使用 Next.js 和 React 构建完整用户界面。
- 通过测试和样例数据验证 grounding、coverage 和 hallucination risk。

可写入简历的示例 bullet：

- Built an evidence-grounded career application agent that converts user profile documents and job descriptions into tailored resume bullets, cover letter drafts, match analysis, and interview preparation notes.
- Implemented a LangGraph-based multi-step workflow for JD parsing, evidence retrieval, match scoring, content generation, and grounding evaluation.
- Designed a RAG pipeline with document chunking, embeddings, Chroma vector search, and source-level citations to reduce unsupported LLM-generated claims.

## 15. 成功标准

MVP 成功的标准不是生成一段看起来漂亮的 cover letter，而是跑通一个可解释、可验证的 agentic AI application。

具体成功标准：

1. 用户可以输入个人材料和岗位 JD。
2. 系统可以提取 JD 的结构化要求。
3. 系统可以从用户材料中检索相关证据。
4. 系统可以生成带证据引用的求职内容。
5. 系统可以标记证据不足或可能编造的内容。
6. 项目可以通过 demo、README 和测试结果展示工程完整性。

如果 MVP 达到以上标准，该项目就可以作为 AI 硕士背景下补足实践经历的代表性项目，并支持申请 agent developer、LLM application engineer 或 AI product engineer 相关岗位。

## 16. Sprint 2 增量：PDF 简历上传与纯文本结构识别

Sprint 2 增加文字型 PDF 简历上传能力，解决用户从 PDF 复制文本时换行混乱、纯文本标题无法被识别为结构化简历 section 的问题。

本增量包含：

1. “个人材料”输入区支持选择单个 `.pdf` 文件。
2. 第一版只处理包含可提取文字层的 PDF，不提供 OCR。
3. 单个 PDF 最大 10 MB。
4. 前端将文件上传到独立的 PDF 解析接口；后端只在内存中读取文件，不落盘、不长期保存。
5. 解析成功后，提取文本自动填入现有文本框，用户可以检查和修改，再触发分析。
6. 解析失败时保留文本框中的原有内容，并展示可操作的错误提示。
7. 纯文本中的独立标题，例如“教育经历”“项目经历”“实习经历”“技能”“奖项”，需要被识别为结构化 section，不要求用户手动添加 Markdown `##`。

明确不包含：

- 扫描件 OCR。
- 多文件合并。
- PDF 永久存储。
- 拖拽上传和复杂文件管理。

成功标准：用户上传一份不超过 10 MB 的文字型中文简历 PDF 后，页面能够展示可编辑的提取文本；后续分析能够正确区分项目、实习、技能和教育 section。
