# CareerPilot Agent

**语言:** [English](README.md) | [简体中文](README.zh-CN.md)

CareerPilot Agent 是一个面向中文求职者的 evidence-grounded agentic LLM application。用户提供真实个人背景材料和目标岗位 JD 后，系统会生成结构化岗位要求、匹配分析、简历要点、面试准备和岗位风险提示，并尽量把输出绑定到用户材料中的证据。

项目定位是一个可展示的 AI 应用作品：后端使用 FastAPI 和 Pydantic 定义 API 与结构化数据契约，LangGraph 负责固定主流程编排，关键节点使用 tool-calling ReAct Agent 做局部多轮推理，检索层提供证据 grounding，中文 Next.js 前端承载完整用户流程。

## 核心能力

- 支持粘贴个人材料，也支持上传文字型 PDF 并提取文本。
- 将简历、项目、实习、技能、教育等内容解析并切分为可检索片段。
- 从 JD 中提取结构化岗位要求，包括重要性、能力标签、验证方式和是否适合面试考察。
- 基于用户自己的材料检索证据，支持 fake/BGE embedding 与 in-memory/Chroma vector store。
- 生成面向用户的安全输出：岗位匹配摘要、匹配分析、3 条简历 bullet、JD 岗位能力问题、简历深挖问题和 top 风险提示。
- 评估 grounding、coverage、specificity、数字声明、重复内容和风险一致性。
- 通过 public output gate 隐藏内部 requirement/evidence/chunk ID，避免把内部追踪字段暴露给用户。
- 对可恢复的 agent 输出失败返回 processing warning，让主体分析结果继续展示，而不是直接暴露原始错误或不安全半成品。

## 当前架构

```text
FastAPI API
  -> LangGraph 固定主流程
      -> parse_inputs
      -> index_profile
      -> jd_analyst
      -> resume_evidence_agent
      -> match_strategist
      -> resume_bullet_agent
      -> interview_prep_agent
      -> risk_auditor_agent
      -> public_output_gate
      -> finalize_response
  -> Pydantic public response

中文 Next.js 前端
  -> 个人材料 / JD 输入
  -> PDF 文本提取
  -> 模型 provider 设置
  -> 模型列表获取
  -> 结果、warning 和 agent trace 展示
```

顶层 LangGraph 保持确定性的固定编排，不让 coordinator 自由调度。只有真正需要语义判断和多轮工具调用的局部节点使用 ReAct：

- `ResumeEvidenceAgent` 使用 tool-calling ReAct 选择简历证据。
- `InterviewPrepAgent` 使用轻量 ReAct 区分 JD 岗位能力考察问题和简历深挖问题。
- `RiskAuditorAgent` 使用岗位类型感知的 ReAct 风险审计，优先展示真实筛选风险，而不是泛软技能缺口。
- JD 分析和简历 bullet 写作仍以一次性 structured LLM 调用为主。

ReAct Agent 使用当前 LangChain 入口：

```python
from langchain.agents import create_agent
```

OpenAI provider 可以传 Pydantic `response_format`。DeepSeek 和 OpenAI-compatible provider 不依赖 Pydantic structured output，而是使用 JSON prompt 加本地 fallback parser，适配不同 provider 的结构化输出差异。

## 模型服务

前端只保留收敛后的 provider 范围：

- 本地演示 provider，用于 deterministic demo 和测试。
- OpenAI。
- DeepSeek。
- OpenAI-compatible chat-completions 接口。

用户可以手动输入模型名，也可以在 UI 中调用 `POST /models/list` 获取远程 provider 的模型列表。API key 仅随请求使用，不写入项目文件。

## API

- `GET /health` 返回 `{ "status": "ok" }`。
- `POST /analysis` 运行完整岗位分析 workflow。
- `POST /models/list` 获取 OpenAI、DeepSeek 或兼容接口的模型列表，返回 `{ models, warning }`。
- `POST /documents/parse-pdf` 提取 10 MB 以内文字型 PDF 的文本。

`POST /analysis` 返回 `AnalysisResponse`，包含状态、公开岗位要求、匹配分析、生成内容、评估报告、风险报告、processing warnings 和 agent traces。内部 ID 会被限制在 public output 边界内。

## 本地开发

后端：

```bash
cd "/Users/baihanshan/Desktop/Career Agent"
conda activate carrer_agent
pip install -r requirements-dev.txt
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
```

前端：

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm install
npm run dev
```

前端默认请求 `http://localhost:8000`。如需指定后端地址：

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

前端检查：

```bash
cd "/Users/baihanshan/Desktop/Career Agent/frontend"
npm run check
npm run build
```

## 检索配置

测试可以使用 deterministic fake embedding 和 in-memory vector store：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

如需本地 BGE + Chroma 检索：

```bash
export BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5
export BGE_MODEL_CACHE_DIR=/Users/baihanshan/Desktop/bge-models
export CHROMA_PATH=/Users/baihanshan/Desktop/career-agent-chroma
```

第一次真实检索运行可能会把 BGE 模型下载到 `BGE_MODEL_CACHE_DIR`。

## Demo 流程

1. 启动后端：

   ```bash
   conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
   ```

2. 启动前端：

   ```bash
   cd frontend
   npm run dev
   ```

3. 打开 `http://localhost:3000`。
4. 将 `backend/tests/fixtures/sample_profile.md` 粘贴到个人材料输入框，或上传文字型 PDF。
5. 将 `backend/tests/fixtures/sample_jd.txt` 粘贴到目标 JD 输入框。
6. 选择本地演示 provider 获取稳定输出，或填写真实 provider API key 和模型名。
7. 运行分析，查看匹配结果、简历 bullet、面试准备、风险提示、processing warnings 和 agent traces。

更详细的演示步骤见 `docs/demo-walkthrough.md`。

## 测试

稳定测试 fixtures 位于 `backend/tests/fixtures/`：

- `sample_profile.md`：包含教育、AI 课程、技能和 GitHub 项目的候选人资料。
- `sample_jd.txt`：包含硬技能、职责和加分项要求的岗位描述。
- `fake_llm_*.json`：为集成测试提供 deterministic LLM 输出。

推荐验证命令：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
cd frontend
npm run check
npm run build
```

## 项目边界

CareerPilot Agent 当前不处理：

- 自动投递。
- 浏览器自动化。
- 多用户登录。
- 支付系统。
- 社交功能。
- 复杂简历排版或文档格式化。

项目重点是展示一个高信号、证据驱动的 AI workflow：agent 架构、检索 grounding、结构化输出、质量门禁，以及可用的中文前端体验。

## 作品集摘要

架构说明和可用于简历的项目 bullet 见 `docs/sprint2/resume-bullets.md`。
