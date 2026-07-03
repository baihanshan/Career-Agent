# CareerPilot Agent 详细设计文档

## 1. 文档目的

本文档基于 `docs/proposal.md` 编写，用于指导 CareerPilot Agent 的 MVP 实现。设计重点是把 proposal 中定义的前端、后端 API、检索层和 agent 工作流拆分成可独立实现、可独立测试的模块。

MVP 的目标不是做一个泛化的求职助手，而是实现一个 evidence-grounded career application agent：用户输入真实个人材料和目标岗位 JD，系统输出有证据支撑的岗位匹配分析、定制化简历 bullet、cover letter 草稿和面试准备建议，并标记证据不足或疑似编造的内容。

## 2. 设计原则

### 2.1 证据优先

所有关于用户经历的生成内容都必须能追溯到用户提供的材料。系统不应把 LLM 的自然语言能力当作事实来源。

### 2.2 模块独立

每个模块应有明确输入、输出和职责边界。文档解析、文本切分、向量检索、JD 解析、匹配评分、写作生成和评估检查都应能用 fixture 独立测试。

### 2.3 显式工作流

使用 LangGraph 定义确定性的状态流转。LLM 只在具体节点内部执行语言理解、推理或写作任务，不负责隐藏控制流。

### 2.4 MVP 优先

第一版聚焦核心闭环：材料输入、JD 解析、证据检索、内容生成、证据评估和前端展示。自动投递、浏览器控制、多用户登录、支付、社交功能和复杂简历排版不进入 MVP。

## 3. 总体架构

系统分为四层：

1. 前端层：Next.js、React、TypeScript。
2. 后端 API 层：FastAPI、Pydantic。
3. 检索层：文本切分、embedding、Chroma 向量库。
4. Agent 工作流层：LangGraph 状态机和多个功能节点。

依赖方向如下：

```text
Frontend
  -> Backend API
      -> Workflow Orchestrator
          -> Document Processing
          -> Retrieval Service
          -> LLM Service
          -> Evaluator
      -> Storage / Vector Store
```

前端只依赖 API response schema，不直接依赖 LangGraph、Chroma 或 LLM provider。Agent 工作流通过服务接口调用检索、LLM 和 evaluator，避免节点代码直接耦合基础设施细节。

## 4. 核心数据模型

### 4.1 ProfileDocument

表示用户上传或粘贴的一份背景材料。

字段：

- `document_id: string`
- `source_name: string`
- `source_type: "text" | "markdown"`
- `content: string`
- `created_at: string`

Sprint 2 的 PDF 上传使用独立解析接口先将文件转换为文本。`POST /analysis` 仍只接收 `text` 和 `markdown`，避免把二进制文件处理与分析工作流耦合。

### 4.2 ProfileChunk

表示可检索的用户材料片段。

字段：

- `chunk_id: string`
- `document_id: string`
- `source_name: string`
- `section_label: string | null`
- `text: string`
- `start_char: number | null`
- `end_char: number | null`
- `embedding_id: string | null`

### 4.3 JDRequirement

表示从岗位 JD 中提取出的结构化要求。

字段：

- `requirement_id: string`
- `category: "responsibility" | "hard_skill" | "soft_skill" | "qualification" | "nice_to_have"`
- `text: string`
- `importance: "high" | "medium" | "low"`
- `keywords: string[]`

### 4.4 EvidenceItem

表示某个岗位要求对应的用户材料证据。

字段：

- `evidence_id: string`
- `requirement_id: string`
- `chunk_id: string`
- `source_name: string`
- `section_label: string | null`
- `snippet: string`
- `score: number`

### 4.5 MatchItem

表示单个岗位要求的匹配结果。

字段：

- `requirement_id: string`
- `match_level: "strong" | "partial" | "weak" | "missing"`
- `rationale: string`
- `evidence_ids: string[]`
- `gap_note: string | null`

### 4.6 GeneratedAssets

表示写作 agent 的生成结果。

字段：

- `match_summary: string`
- `resume_bullets: ResumeBullet[]`
- `cover_letter: CoverLetterDraft`
- `interview_prep: InterviewPrepItem[]`

`ResumeBullet` 字段：

- `text: string`
- `target_requirement_ids: string[]`
- `evidence_ids: string[]`
- `risk_level: "low" | "medium" | "high"`

`CoverLetterDraft` 字段：

- `opening: string`
- `body: string[]`
- `closing: string`
- `evidence_ids: string[]`

`InterviewPrepItem` 字段：

- `topic: string`
- `why_it_matters: string`
- `supporting_evidence_ids: string[]`
- `prep_suggestion: string`

### 4.7 EvaluationReport

表示 evaluator 的检查结果。

字段：

- `grounding_warnings: GroundingWarning[]`
- `coverage_gaps: CoverageGap[]`
- `specificity_notes: string[]`
- `risk_summary: string`
- `overall_status: "pass" | "pass_with_warnings" | "fail"`

`GroundingWarning` 字段：

- `asset_type: "resume_bullet" | "cover_letter" | "match_summary" | "interview_prep"`
- `asset_id: string`
- `claim: string`
- `reason: string`
- `severity: "low" | "medium" | "high"`

## 5. 后端 API 设计

### 5.1 API 模块职责

后端 API 模块负责接收输入、校验请求、调用工作流、返回结构化结果。它不负责具体文本切分、embedding、JD 解析或写作逻辑。

### 5.2 Endpoints

#### GET `/health`

用途：健康检查。

Response:

```json
{
  "status": "ok"
}
```

#### POST `/analysis`

用途：创建一次完整分析任务。MVP 可以先同步返回结果；如果生成时间过长，再演进为异步任务模式。

Request:

```json
{
  "profile_documents": [
    {
      "source_name": "resume.md",
      "source_type": "markdown",
      "content": "..."
    }
  ],
  "job_description": "...",
  "run_config": {
    "model": "default",
    "temperature": 0.2,
    "top_k": 5
  }
}
```

Response:

```json
{
  "analysis_id": "analysis_123",
  "status": "completed",
  "result": {
    "jd_requirements": [],
    "evidence_table": [],
    "match_analysis": [],
    "generated_assets": {},
    "evaluation_report": {}
  }
}
```

### 5.3 API 校验规则

- `profile_documents` 至少包含一项。
- `job_description` 不能为空。
- 单个文档内容为空时返回 validation error。
- 不支持的 `source_type` 返回 validation error。PDF 文件必须先通过 PDF 解析接口转换为文本，再进入分析接口。
- MVP 对超长输入先返回 warning 或截断策略，由 document processing 模块执行。

### 5.4 API 可测试点

- `GET /health` 返回 `status: ok`。
- 空 profile documents 被拒绝。
- 空 JD 被拒绝。
- 不支持的 source type 被拒绝。
- valid request 能调用 workflow 并返回符合 schema 的 response。

## 6. 文档处理模块设计

### 6.1 模块职责

文档处理模块负责把用户材料转成规范文本，并切分成可检索 chunks。

不负责：

- 生成 embeddings。
- 调用 LLM。
- 判断岗位匹配。
- 生成求职内容。

### 6.2 输入输出

输入：

- `ProfileDocument[]`

输出：

- `ProfileChunk[]`
- `ProcessingWarning[]`

### 6.3 文本标准化

标准化步骤：

1. 去除首尾空白。
2. 统一换行符。
3. 保留 Markdown 标题，用于推断 `section_label`。
4. 过滤连续过多空行。
5. 对过短文档生成 warning，但不直接中断流程。

### 6.4 Chunking 策略

MVP 使用基于段落和标题的 chunking：

- 优先按 Markdown heading 分段。
- 每个 chunk 控制在合理长度内。
- 保留 source name、section label 和字符位置。
- 如果一个段落过长，再按句子或固定 token 近似长度切分。

### 6.5 文档处理可测试点

- Markdown 标题能被识别为 section label。
- chunk metadata 包含 source name 和 chunk id。
- 空文档返回 warning 或 validation error。
- 长文本能被切成多个 chunks。
- chunk 顺序稳定，便于 fixture 测试。

## 7. 检索模块设计

### 7.1 模块职责

检索模块负责 embedding、向量存储和证据检索。

不负责：

- 解析 JD。
- 生成简历 bullet。
- 判断最终 grounding 是否通过。

### 7.2 主要接口

#### `index_profile(chunks: ProfileChunk[]) -> IndexedProfile`

职责：

- 为 chunks 生成 embeddings。
- 写入 Chroma collection。
- 返回 collection id 或 profile index id。

#### `retrieve_evidence(requirements: JDRequirement[], top_k: number) -> EvidenceItem[]`

职责：

- 为每个 requirement 构造检索 query。
- 从 Chroma 中检索相关 chunks。
- 返回带 source metadata 的 evidence items。

### 7.3 Collection 策略

MVP 可以为每次 analysis 创建独立 collection 或使用带 `analysis_id` metadata 的共享 collection。为了降低串数据风险，MVP 优先使用每次 analysis 独立 collection。

### 7.4 Evidence snippet 策略

Evidence snippet 应来自原始 chunk 文本，不由 LLM 改写。这样前端展示的证据可以追溯到用户原文。

### 7.5 检索可测试点

- indexing 后每个 chunk 都有可追踪 metadata。
- retrieve result 包含 `chunk_id`、`source_name`、`snippet` 和 `score`。
- 对固定 sample query 能返回预期相关 chunk。
- 当没有足够相关证据时，返回空列表或低分 evidence，而不是伪造证据。

## 8. LLM 服务模块设计

### 8.1 模块职责

LLM 服务模块封装模型调用、prompt 模板和 structured output 解析。LangGraph 节点通过该模块调用模型。

### 8.2 主要能力

- `extract_jd_requirements(job_description) -> JDRequirement[]`
- `summarize_evidence(requirement, evidence_items) -> string`
- `generate_application_assets(context) -> GeneratedAssets`
- `evaluate_claim_grounding(claims, evidence_items) -> GroundingWarning[]`

### 8.3 Structured Output

所有需要进入后续流程的 LLM 输出都应被解析为 Pydantic model。解析失败时返回可恢复错误，由 workflow 决定是否重试。

### 8.4 LLM 可测试点

MVP 测试不依赖真实模型稳定性。应提供 fake LLM client：

- 固定 JD 输入返回固定 requirements。
- 固定 evidence 输入返回固定 generated assets。
- malformed output 能触发 parser error。

## 9. LangGraph 工作流设计

### 9.1 Workflow State

工作流状态包含：

- `analysis_id`
- `profile_documents`
- `job_description`
- `run_config`
- `profile_chunks`
- `processing_warnings`
- `jd_requirements`
- `retrieved_evidence`
- `match_analysis`
- `generated_assets`
- `evaluation_report`
- `errors`

### 9.2 节点设计

#### `parse_inputs`

职责：

- 标准化输入。
- 生成 `analysis_id`。
- 检查必要字段。

输入：

- API request

输出：

- 初始化后的 workflow state

独立测试：

- valid request 能生成 analysis id。
- invalid request 产生明确 error。

#### `index_profile`

职责：

- 调用文档处理模块生成 chunks。
- 调用检索模块建立 profile index。

输入：

- `profile_documents`

输出：

- `profile_chunks`
- `processing_warnings`

独立测试：

- sample documents 生成预期 chunks。
- embedding/indexing 失败时写入 errors。

#### `analyze_jd`

职责：

- 调用 LLM 服务提取 JD requirements。
- 按重要性和类别结构化输出。

输入：

- `job_description`

输出：

- `jd_requirements`

独立测试：

- sample JD 生成固定结构。
- LLM malformed output 能被捕获。

#### `retrieve_evidence`

职责：

- 对每个 JD requirement 检索相关 profile chunks。
- 生成 evidence table。

输入：

- `jd_requirements`
- `profile_chunks`

输出：

- `retrieved_evidence`

独立测试：

- 每个 high importance requirement 至少执行一次检索。
- 无证据 requirement 不被误标为 strong match。

#### `score_match`

职责：

- 根据 evidence score、requirement importance 和 evidence 内容生成匹配结果。
- 标记 strong、partial、weak 或 missing。

输入：

- `jd_requirements`
- `retrieved_evidence`

输出：

- `match_analysis`

独立测试：

- 有高分证据时可判定 strong 或 partial。
- 无证据时判定 missing。
- 低分证据时判定 weak。

#### `write_application`

职责：

- 基于 JD requirements、evidence 和 match analysis 生成求职内容。
- 每条 resume bullet 必须携带 `evidence_ids`。

输入：

- `jd_requirements`
- `retrieved_evidence`
- `match_analysis`

输出：

- `generated_assets`

独立测试：

- 每条 bullet 至少关联一个 evidence id，除非明确标记 high risk。
- cover letter 不包含 evidence 中不存在的雇主、指标或工具。

#### `evaluate_grounding`

职责：

- 检查 generated assets 中的声明是否被 evidence 支撑。
- 标记 unsupported claims、coverage gaps、specificity notes 和 risk summary。

输入：

- `generated_assets`
- `retrieved_evidence`
- `jd_requirements`

输出：

- `evaluation_report`

独立测试：

- 对包含编造数字的 fixture 能产生 high severity warning。
- 对遗漏 high importance requirement 的输出能产生 coverage gap。

#### `finalize_response`

职责：

- 整理 API response。
- 合并 warnings 和 errors。
- 生成前端可直接渲染的数据结构。

输入：

- 完整 workflow state

输出：

- API response result

独立测试：

- completed state 能生成完整 response。
- 有 warning 的 state 能保留 warning。
- fail state 不返回伪完成结果。

### 9.3 工作流错误策略

- validation error：中断流程并返回可读错误。
- document processing warning：不中断流程。
- vector store failure：中断生成，返回 indexing error。
- LLM parser error：重试一次；仍失败则中断对应节点。
- weak evidence：不中断流程，但在 match analysis 和 evaluation report 中标记。

## 10. 匹配评分设计

### 10.1 输入

- JD requirements
- Evidence items

### 10.2 评分规则

MVP 使用可解释规则，不直接让 LLM 给最终分数。

建议规则：

- `strong`：存在高相关 evidence，且 evidence 明确覆盖 requirement。
- `partial`：存在相关 evidence，但覆盖不完整。
- `weak`：只有低相关 evidence，或 evidence 只能间接支持。
- `missing`：没有可用 evidence。

### 10.3 输出

每个 requirement 生成一个 MatchItem，包含 match level、理由、证据 id 和 gap note。

### 10.4 可测试点

- 无 evidence 的 requirement 必须是 missing。
- low score evidence 不应生成 strong。
- 每个 MatchItem 的 evidence id 必须能在 evidence table 中找到。

## 11. 写作生成设计

### 11.1 生成内容

写作 agent 生成四类内容：

1. 岗位匹配总结。
2. 定制化简历 bullet。
3. Cover letter 草稿。
4. 面试准备建议。

### 11.2 生成约束

写作 prompt 必须明确：

- 只能基于 evidence 写用户经历。
- 不得编造雇主、日期、数字、项目结果或工具。
- 证据不足时应降低语气或标记风险。
- 每条具体经历声明必须绑定 evidence id。

### 11.3 Resume Bullet 设计

每条 bullet 应包含：

- 面向哪个 JD requirement。
- 使用了哪些 evidence。
- 输出文本。
- risk level。

### 11.4 Cover Letter 设计

Cover letter 草稿应保持可编辑，不追求最终定稿。它应围绕岗位要求和用户真实证据展开，并避免夸大。

### 11.5 Interview Prep 设计

面试准备建议应从 JD gaps 和 strong matches 中生成：

- strong match 用于准备项目讲述。
- partial 或 weak match 用于准备补充学习计划。
- missing requirement 用于提示风险。

### 11.6 可测试点

- 生成内容中引用的 evidence ids 都存在。
- high risk bullet 能被 evaluator 识别。
- 没有 evidence 的 requirement 不应生成自信经历陈述。

## 12. Evaluator 设计

### 12.1 评估目标

Evaluator 的目标是降低 hallucination 风险，让用户知道哪些内容可靠、哪些内容需要人工修改。

### 12.2 检查项

#### Grounding

检查生成内容中的经历声明是否被 evidence 支撑。

#### Coverage

检查 high importance JD requirements 是否被匹配分析或生成内容覆盖。

#### Specificity

检查简历 bullet 是否过于泛泛，例如只写“熟悉 AI 技术”，但没有具体项目、课程或任务。

#### Risk

检查是否出现 evidence 中不存在的数字、雇主、日期、工具、项目成果或职责范围。

### 12.3 评估实现

MVP 可以采用规则检查和 LLM 判断结合：

- 规则检查：evidence id 是否存在、数字是否来自 evidence、requirement 是否覆盖。
- LLM 判断：claim 是否被 snippet 语义支持。

### 12.4 可测试点

- 编造数字被标记。
- 无 evidence id 的 bullet 被标记。
- 未覆盖 high importance requirement 被标记。
- evidence 足够的 claim 不应被误判为 high severity。

## 13. 前端设计

### 13.1 页面结构

MVP 使用单页应用结构：

1. 输入区：profile materials 和 job description。
2. 运行状态区：indexing、analysis、generation、evaluation。
3. 结果区：match summary、evidence table、resume bullets、cover letter、interview prep。
4. 风险区：grounding warnings 和 coverage gaps。

### 13.2 输入区

输入区支持：

- 粘贴个人材料。
- 粘贴 JD。
- 上传文字型 PDF，并将解析结果回填到个人材料文本框。

PDF 上传和分析提交是两个独立动作；用户可以在提交分析前检查和编辑提取文本。

### 13.3 结果展示

结果展示需要突出 evidence：

- Resume bullet 旁展示 evidence source。
- Match analysis 按 requirement 展示 strong、partial、weak、missing。
- Cover letter 可展示整体 evidence references。
- Interview prep 展示对应 requirement 和 supporting evidence。

### 13.4 风险展示

风险展示应清楚但不过度打断用户：

- high severity warning 显示在相关内容旁。
- coverage gaps 单独列出。
- weak match 用标签展示。

### 13.5 前端可测试点

- 空输入时提交按钮不可用或返回清楚错误。
- loading 状态能正确显示。
- completed response 能渲染所有结果区块。
- warning response 能渲染风险提示。
- evidence source 能显示在对应输出旁。

## 14. 错误处理设计

### 14.1 错误类型

- `ValidationError`
- `DocumentProcessingError`
- `VectorStoreError`
- `LLMCallError`
- `LLMOutputParseError`
- `WorkflowError`

### 14.2 用户可见错误

用户不需要看到内部 stack trace。API 应返回可读 message 和可选 technical code。

示例：

```json
{
  "status": "failed",
  "error": {
    "code": "VECTOR_STORE_ERROR",
    "message": "Profile materials could not be indexed. Please try again."
  }
}
```

### 14.3 Warning 与 Error 区分

warning 不阻断流程，例如：

- 用户资料较短。
- 某些 requirement 证据较弱。
- JD 被截断。

error 阻断流程，例如：

- 输入为空。
- 向量库写入失败。
- LLM 输出无法解析且重试失败。

## 15. 测试设计

### 15.1 单元测试

单元测试覆盖独立模块：

- Pydantic schema validation。
- 文档标准化与 chunking。
- JD requirement parser。
- Retrieval service。
- Match scorer。
- Writer output parser。
- Evaluator。

### 15.2 Workflow 测试

使用 fake LLM、fake embedding 和临时 vector store 测试 LangGraph workflow：

- valid sample input 能到达 final response。
- vector store failure 能中断在 index_profile。
- malformed LLM output 能触发重试和错误处理。
- weak evidence 能继续流程并出现在 warnings 中。

### 15.3 API 测试

API 测试覆盖：

- health endpoint。
- request validation。
- successful analysis response shape。
- failed analysis response shape。

### 15.4 前端测试

前端测试覆盖：

- 输入表单渲染。
- 提交状态切换。
- 结果区块渲染。
- warning 和 evidence citation 渲染。

### 15.5 集成测试

集成测试使用一份小型 sample profile 和 sample JD，验证：

- 能生成完整 response。
- 至少提取一个 JD requirement。
- 至少返回一个 evidence item。
- 生成的 resume bullet 包含 evidence id。
- evaluator report 存在并可渲染。

## 16. 推荐目录结构

建议后续实现时使用以下结构：

```text
careerpilot/
  backend/
    app/
      main.py
      api/
        routes.py
        schemas.py
      core/
        config.py
        errors.py
      documents/
        parser.py
        chunker.py
        models.py
      retrieval/
        embeddings.py
        vector_store.py
        service.py
      llm/
        client.py
        prompts.py
        structured_outputs.py
      workflow/
        state.py
        graph.py
        nodes.py
      evaluation/
        evaluator.py
      tests/
        fixtures/
  frontend/
    app/
    components/
    lib/
    tests/
  docs/
    proposal.md
    detailed-design.md
```

该目录结构只是实现建议。核心要求是模块边界清晰，测试可以按模块独立运行。

## 17. MVP 交付标准

MVP 完成时应满足：

1. 用户可以输入个人材料和岗位 JD。
2. 后端可以解析和切分个人材料。
3. 检索层可以返回带 metadata 的 evidence。
4. LangGraph workflow 可以完成 JD 分析、证据检索、匹配评分、内容生成和评估。
5. 生成内容包含 evidence references。
6. Evaluator 可以标记 unsupported claims 和 coverage gaps。
7. 前端可以展示结果、证据和风险提示。
8. 核心模块有独立测试，完整 workflow 有 fixture 集成测试。

## 18. 非 MVP 范围

以下内容不进入第一版详细设计：

- 自动投递职位。
- 浏览器自动化。
- 多用户账号系统。
- 支付或订阅。
- 社交分享功能。
- 高级简历排版编辑器。
- 多语言简历自动转换。
- 扫描件 PDF OCR。

这些能力可以在核心 evidence-grounded workflow 稳定后再设计。

## 19. 后续扩展方向

MVP 稳定后可以考虑：

- 扫描件 PDF OCR 和版面感知解析。
- LangSmith 或 Ragas 评估集成。
- 多 JD 对比分析。
- GitHub repository 自动总结。
- 简历版本管理。
- 面试问答模拟。
- 部署到云端并提供 demo 环境。

扩展时仍应保持同一原则：新模块通过明确接口接入，不破坏现有核心工作流的可测试性。

## 20. Sprint 2 PDF 简历上传详细设计

### 20.1 范围与约束

第一版只支持单个文字型 PDF，文件大小上限为 10 MB。扫描件、图片型 PDF、OCR、多文件合并、文件持久化和拖拽上传不在本次范围内。

后端解析过程只使用请求内存中的文件内容。请求完成后不保留原始 PDF，解析文本由前端回填到现有输入框，用户确认或编辑后再提交分析。

### 20.2 组件边界

新增组件及职责：

- `frontend/components/ProfileInput.tsx`：选择 PDF、展示上传状态和解析错误、将成功结果回填文本框。
- `frontend/lib/api.ts`：使用 `multipart/form-data` 调用 PDF 解析接口。
- `backend/app/api/routes.py`：接收上传文件，执行类型和大小校验，映射受控错误响应。
- `backend/app/documents/pdf_parser.py`：从 PDF 字节中提取逐页文本并规范化，不处理 HTTP 或工作流逻辑。
- `backend/app/documents/chunker.py`：识别 Markdown 标题和纯文本独立标题，生成结构化 section metadata。

PDF 解析不进入 LangGraph。只有用户确认后的文本才通过现有 `POST /analysis` 进入 workflow。

### 20.3 API 设计

新增 endpoint：

```text
POST /documents/parse-pdf
Content-Type: multipart/form-data
field: file
```

成功响应：

```json
{
  "source_name": "resume.pdf",
  "page_count": 2,
  "text": "叶飞\n教育经历\n..."
}
```

校验规则：

- 文件名扩展名必须为 `.pdf`，并校验上传内容类型。
- 文件不得为空，且不得超过 10 MB。
- PDF 必须可读取且未被密码保护。
- 所有页面完成提取和规范化后，文本不能为空。

受控错误码：

- `PDF_INVALID_TYPE`：不是 PDF。
- `PDF_TOO_LARGE`：超过 10 MB。
- `PDF_EMPTY`：文件为空。
- `PDF_ENCRYPTED`：PDF 需要密码。
- `PDF_CORRUPT`：文件损坏或无法解析。
- `PDF_NO_TEXT`：未提取到文字，提示用户使用文字型 PDF 或粘贴文本。

### 20.4 文本提取与规范化

后端使用 `pypdf` 逐页提取文字。页面之间保留一个空行；统一 `CRLF/CR` 为 `LF`，移除行尾多余空白，将三个以上连续空行压缩为两个空行。解析器不尝试猜测或改写简历内容。

解析结果只代表 PDF 的文字层。若 PDF 的视觉顺序与内部文字顺序不一致，用户可以在回填后的文本框中修正。

### 20.5 纯文本简历结构识别

纯文本和没有 Markdown `#` 标记的粘贴内容都需要识别独立标题行。支持的标题至少包括：

- 中文：`教育经历`、`教育背景`、`项目经历`、`项目经验`、`实习经历`、`工作经历`、`技能`、`专业技能`、`奖项`、`荣誉奖项`、`其他`。
- 英文：`Education`、`Projects`、`Project Experience`、`Internship`、`Experience`、`Work Experience`、`Skills`、`Awards`、`Other`。

只有整行匹配标题词时才切换 section，避免把“参与项目经历复盘”等正文误识别为标题。`project` 和 `internship` section 继续保留较完整上下文，再按最大长度安全切分。

上传 PDF 后，前端提交分析时使用：

```json
{
  "source_name": "resume.pdf",
  "source_type": "text",
  "content": "用户确认后的提取文本"
}
```

### 20.6 前端交互

“个人材料”区域保留原有文本框，并增加“上传 PDF”文件选择控件。

交互规则：

1. 选择文件后立即开始解析，显示“正在解析 PDF…”。
2. 解析成功后用提取文本替换文本框内容，并显示文件名和页数。
3. 只有解析成功才覆盖文本框；失败时保留原内容。
4. 上传或解析期间禁用重复上传，但不阻止用户查看其他输入。
5. 用户仍需点击“开始分析”，PDF 解析成功不自动触发分析。

### 20.7 测试设计

后端单元测试覆盖：

- 多页文字型 PDF 能返回页数和规范文本。
- 空白 PDF 返回 `PDF_NO_TEXT`。
- 加密、损坏、空文件、非 PDF 和超过 10 MB 文件返回对应错误。
- 纯文本独立中文和英文标题能映射到正确 section。
- 正文中包含标题关键词时不会误切分。

API 测试覆盖 multipart 上传、成功响应 schema 和受控错误码。前端检查覆盖文件控件、解析中状态、成功回填、失败保留原文本和错误文案。完整回归测试需要确认现有粘贴文本和 Markdown 输入仍能正常分析。
