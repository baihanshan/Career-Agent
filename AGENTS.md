# AGENTS.md

<!-- PROJECT_MEMORY_SECTION_BEGIN -->

## 项目记忆

本项目使用本地长期记忆目录 `project_memory/`。

每次在本项目开启新的 Codex 会话时，使用 `project-memory` skill，并遵循以下启动协议：

1. 先读取 `project_memory/handoff.md`，尤其是最新的 `## 当前上下文` 部分，把它作为快速恢复状态。
2. 再读取 `project_memory/index.md`，把它作为有限的记忆路由层。
3. 不要加载所有记忆文件。只有当 handoff 或 index 表明相关时，才读取详细记忆文件。
4. 如果用户说“继续”“恢复”“接着上次”“检查项目上下文”，或要求处理 project-memory 相关工作，在编辑代码前先应用此协议。

完成复杂任务前，如果产生了值得长期保留的项目知识，需要更新项目记忆。复杂任务包括：修复 bug、作出架构决策、修改 API 契约、改动多个文件、改变运行/测试/构建/环境命令，或留下需要后续接手的未完成状态。

不要在项目记忆中保存密钥、令牌或其他秘密信息。临时记忆可以自动删除；重要记忆在删除前必须得到用户明确确认。

<!-- PROJECT_MEMORY_SECTION_END -->

# 项目介绍

CareerPilot Agent 是一个面向求职者的 agentic LLM application。用户输入真实个人背景材料和目标岗位 JD 后，系统会基于材料证据生成岗位匹配摘要、简历要点、面试准备和风险提示。项目采用 FastAPI 后端、LangGraph 工作流、Pydantic 结构化模型、本地/真实 LLM provider、BGE/Chroma 检索，以及中文 Next.js 前端。

## 仓库结构导航

```text
.
├── backend/                 # FastAPI 后端、文档处理、检索、LLM、workflow 和测试
├── frontend/                # Next.js 中文前端
├── docs/                    # 设计文档、sprint 任务拆解、修复方案和演示文档
├── project_memory/          # Codex 项目长期记忆数据
├── AGENTS.md                # 给 Codex/agent 的项目说明与工作约定
├── README.md                # 英文项目说明与运行方式
├── README.zh.md             # 中文项目说明与运行方式
├── pyproject.toml           # 后端生产依赖
└── requirements-dev.txt     # 后端开发/测试依赖
```

## 后端结构

后端代码集中在 `backend/app/`：

```text
backend/app/
├── main.py                  # FastAPI app 入口，注册 CORS、异常处理和路由
├── api/
│   ├── routes.py            # `/health`、`/analysis`、`/documents/parse-pdf`
│   └── schemas.py           # API request/response 与公开 schema
├── core/
│   └── errors.py            # 统一错误码、warning、AppError
├── documents/
│   ├── parser.py            # ProfileDocument 解析入口
│   ├── chunker.py           # 简历 section/chunk 切分与标题识别
│   ├── experience_parser.py # 项目/实习拆成 ExperienceRecord
│   ├── pdf_parser.py        # 文字型 PDF 内存解析
│   └── models.py            # 文档与 chunk 数据模型
├── retrieval/
│   ├── embeddings.py        # Fake/BGE embedding client
│   ├── vector_store.py      # In-memory/Chroma vector store
│   └── service.py           # 简历索引和 evidence 检索服务
├── llm/
│   ├── client.py            # 一次性 LLM client，支持 OpenAI/DeepSeek/OpenAI-compatible
│   ├── react_model.py       # LangChain tool-calling ReAct ChatModel 适配
│   ├── prompts.py           # Prompt 模板
│   └── structured_outputs.py# LLM structured output 解析与归一化
├── evaluation/
│   ├── evaluator.py         # grounding/coverage/specificity 评估
│   ├── numeric_claims.py    # 数字声明分类与 grounding
│   └── quality_gate.py      # ID 泄露、重复、复制率、风险一致性等质量门禁
└── workflow/
    ├── graph.py             # LangGraph 固定主流程
    ├── nodes.py             # workflow 节点实现和错误包装
    ├── state.py             # AnalysisState
    ├── service.py           # 默认服务装配入口
    ├── domain_models.py     # workflow 内部领域模型
    ├── react_tools.py       # 结构化 ReAct 工具
    ├── agent_tools.py       # trace 兼容工具/摘要
    ├── resume_evidence_agent.py
    ├── interview_prep_agent.py
    ├── risk_auditor_agent.py
    ├── match_scoring.py
    ├── writer.py
    └── public_output.py     # internal/public 输出边界
```

## 后端主流程

主流程由 `backend/app/workflow/graph.py` 固定编排，节点顺序为：

```text
parse_inputs
→ index_profile
→ jd_analyst
→ resume_evidence_agent
→ match_strategist
→ resume_bullet_agent
→ interview_prep_agent
→ risk_auditor_agent
→ public_output_gate
→ finalize_response
```

关键约定：

- 顶层 LangGraph 保持固定编排，不让 coordinator 自由调度。
- `ResumeEvidenceAgent`、`InterviewPrepAgent`、`RiskAuditorAgent` 使用真实 tool-calling ReAct Agent。
- ReAct Agent 工厂使用最新 LangChain 入口 `from langchain.agents import create_agent`，不要再使用旧的 `langgraph.prebuilt.create_react_agent`。
- `create_agent(..., response_format=...)` 只对 OpenAI provider 传 Pydantic schema。DeepSeek 和 openai-compatible provider 不传 Pydantic `BaseModel`，而是依赖 prompt 中的 JSON 示例和本地 fallback parser 解析最终 AI message。
- `JD Analyst` 和 `Resume Bullet` 仍主要使用一次性 structured LLM 调用。
- 内部可以保留 evidence/requirement/chunk ID，但用户可见输出必须经过 `public_output_gate`，不能泄露内部 ID。
- 关键 ReAct Agent 失败时返回受控错误，不展示半成品。

## 前端结构

前端代码集中在 `frontend/`：

```text
frontend/
├── app/
│   ├── page.tsx             # 页面状态、分析请求、结果渲染编排
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ProfileInput.tsx     # 个人材料输入与 PDF 上传解析
│   ├── JobDescriptionInput.tsx
│   ├── LlmSettings.tsx      # provider/model/API key 设置
│   ├── ResultView.tsx       # 匹配摘要、简历要点、面试准备、trace
│   ├── RiskWarnings.tsx
│   ├── ProcessingWarnings.tsx
│   └── RunStatus.tsx
├── lib/
│   ├── api.ts               # `/analysis` 与 `/documents/parse-pdf` API client
│   └── types.ts             # 前端 TypeScript API 类型
├── scripts/
│   └── verify-structure.mjs # 前端结构检查
├── package.json
└── tsconfig.json
```

前端默认请求 `http://localhost:8000`。如需指定后端地址，启动时设置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## 文档与测试结构

```text
docs/
├── proposal.md              # 初始产品提案
├── detailed-design.md       # MVP 详细设计
├── demo-walkthrough.md      # 本地演示流程
├── docker-strategy.md       # Docker 策略说明
├── specs/                   # 项目规格文档，中英文版本
├── sprint1/tasks/           # MVP/sprint1 任务拆解与进度
└── sprint2/                 # Sprint 2 架构升级、质量修复和 PDF 上传资料

backend/tests/
├── fixtures/                # sample profile/JD、fake LLM、ReAct tool-call fixtures
├── test_api.py
├── test_workflow_*.py
├── test_*_agent.py
├── test_quality_gate.py
├── test_public_output.py
└── ...                      # 文档处理、检索、LLM、评估、前端契约等专项测试
```

Sprint 2 的核心背景在：

- `docs/sprint2/improve.md`
- `docs/sprint2/tasks/progress.md`
- `docs/sprint2/fix_problem.md`
- `docs/sprint2/fix_solution.md`
- `docs/sprint2/fix_tasks/progress.md`

## 常用运行命令

后端：

```bash
cd "/Users/baihanshan/Desktop/Career Agent"
conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
```

前端：

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm run dev
```

后端测试：

```bash
cd "/Users/baihanshan/Desktop/Career Agent"
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

前端检查与构建：

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm run check
npm run build
```

健康检查：

```bash
curl http://localhost:8000/health
```

## 调试提示

- 前端报“分析失败”但后端终端没有 stack trace 时，优先查看浏览器 DevTools 的 Network `/analysis` response。
- `REACT_OUTPUT_PARSE_ERROR` 通常表示某个 ReAct Agent 的模型输出未能解析成后端要求的结构化结果。
- 用户提供的 API key 不会写入项目文件；不要把 API key、token、cookie 或 `.env` 真实值写进文档或项目记忆。
- 如果需要复现真实模型问题，优先保存脱敏后的 request payload、response JSON、agent 名称、错误码和关键日志。

# 实践约束

- 在调试 bug 的时候，不要自己进行操作电脑，告诉我我应该如何做调出报错日志，然后由我来将这个报错日志发给你
