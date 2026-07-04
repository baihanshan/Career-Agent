# CareerPilot Agent

**语言:** [English](README.md) | [简体中文](README.zh-CN.md)

CareerPilot Agent 是一个本地运行的 AI 求职助手。你提供个人简历、项目经历或职业材料，再粘贴目标岗位 JD，它会帮你判断岗位匹配度、提炼简历要点、准备面试问题，并指出申请中可能被筛掉的风险。

这个项目目前是本地 Web App。它既可以作为求职辅助工具的 demo，也可以作为一个展示 evidence-grounded LLM workflow 的工程作品。

## 你可以用它做什么

- 粘贴简历、项目、实习、技能和教育经历。
- 上传文字型 PDF 并提取内容。
- 粘贴目标岗位 JD。
- 生成岗位匹配摘要和逐条岗位要求分析。
- 得到 3 条基于真实经历证据的简历 bullet 草稿。
- 准备 JD 能力考察问题和简历深挖问题。
- 查看风险提示，例如硬技能缺口、证据不足、项目影响描述不清等。
- 使用本地演示模式，或接入 OpenAI、DeepSeek、OpenAI-compatible 模型服务。

## 你需要准备什么

- 一台可以运行 Python 和 Node.js 的电脑。
- 文本、Markdown 或文字型 PDF 格式的个人材料。
- 一个目标岗位 JD。
- 可选：OpenAI、DeepSeek 或兼容接口的 API key，用于真实模型输出。

本地演示模式不需要 API key，但它是 deterministic demo，不同输入可能会得到风格相近的输出。

## 快速开始

克隆仓库并启动后端：

```bash
git clone https://github.com/baihanshan/Career-Agent.git
cd Career-Agent
conda create -n carrer_agent python=3.11 -y
conda activate carrer_agent
pip install -r requirements-dev.txt
conda run -n carrer_agent uvicorn backend.app.main:app --reload --log-level debug
```

另开一个终端启动前端：

```bash
cd Career-Agent/frontend
npm install
npm run dev
```

打开：

```text
http://localhost:3000
```

前端默认请求 `http://localhost:8000`。如果你的后端地址不同，可以这样启动前端：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## 如何使用

1. 添加个人材料。
   粘贴简历文本、项目经历、实习描述，或上传文字型 PDF。

2. 添加目标岗位 JD。
   使用真实准备投递的岗位描述。JD 越具体，分析通常越有参考价值。

3. 选择模型服务。
   想快速演示可以用本地演示模式；想看真实模型输出，可以填写自己的 OpenAI、DeepSeek 或兼容接口 API key。

4. 运行分析。
   系统会解析个人材料、提取 JD 要求、检索支持证据、生成简历和面试建议，并检查风险。

5. 查看结果。
   用匹配分析判断是否值得投递，用简历 bullet 作为修改素材，用面试准备部分整理具体回答。

## 如何理解结果

- **匹配摘要：** 快速概括你和岗位的匹配度与主要缺口。
- **岗位要求分析：** 展示每条 JD 要求是 strong、partial、weak 还是 missing。
- **简历 bullet：** 基于你真实经历生成的简历要点草稿，需要你再按目标简历风格微调。
- **面试准备：** 分为 JD 能力考察问题和简历深挖问题，帮助你准备回答思路。
- **风险提示：** 标出可能影响筛选或面试的短板。
- **Processing warnings：** 工作流中的可恢复问题。如果主体结果已经展示，通常表示某个环节降级了，而不是整次分析失败。

## 隐私说明

- 这个项目面向本地开发和演示使用。
- UI 中填写的 API key 会随分析请求发送，但不会写入项目文件。
- 不要把真实 API key、完整简历或私人岗位材料提交到仓库。
- 如果使用真实模型 provider，你提交的内容会发送给对应 provider，并受其服务条款约束。

## 常见问题

- **后端连不上：** 确认 `uvicorn` 正在 `http://localhost:8000` 运行。
- **前端分析失败：** 查看浏览器 Network 里的 `/analysis` response。
- **PDF 上传失败：** 使用 10 MB 以内、未加密、可复制文字的 PDF，或直接粘贴文本。
- **模型列表获取失败：** 检查 provider、API key 和 Base URL。兼容接口的 Base URL 通常应指向 OpenAI-compatible 根路径，例如 `/v1`。
- **真实模型输出失败：** 先切到本地演示模式，确认应用本身能正常运行。

## 面向开发者

CareerPilot Agent 是一个 evidence-grounded LLM application：顶层 workflow 固定，关键语义判断环节使用局部 ReAct Agent。

### 架构

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

### API

- `GET /health` 返回 `{ "status": "ok" }`。
- `POST /analysis` 运行完整岗位分析 workflow。
- `POST /models/list` 获取 OpenAI、DeepSeek 或兼容接口的模型列表，返回 `{ models, warning }`。
- `POST /documents/parse-pdf` 提取 10 MB 以内文字型 PDF 的文本。

`POST /analysis` 返回 `AnalysisResponse`，包含状态、公开岗位要求、匹配分析、生成内容、评估报告、风险报告、processing warnings 和 agent traces。内部 ID 会被限制在 public output 边界内。

### 检索配置

测试可以使用 deterministic fake embedding 和 in-memory vector store：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

如需本地 BGE + Chroma 检索：

```bash
export BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5
export BGE_MODEL_CACHE_DIR=/path/to/bge-models
export CHROMA_PATH=/path/to/career-agent-chroma
```

第一次真实检索运行可能会把 BGE 模型下载到 `BGE_MODEL_CACHE_DIR`。

### 验证

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
cd frontend
npm run check
npm run build
```

稳定测试 fixtures 位于 `backend/tests/fixtures/`。

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

## License

本项目使用 [MIT License](LICENSE)。
