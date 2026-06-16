# CareerPilot Agent

CareerPilot Agent 是一个以证据为中心的求职申请助手。MVP 会把用户提供的职业背景材料和目标岗位 JD，转化为结构化岗位匹配分析、简历 bullet、cover letter 草稿、面试准备建议，并展示对应证据或风险提示。

## MVP 范围

- 粘贴或上传个人职业材料。
- 粘贴目标岗位描述。
- 解析并切分个人材料。
- 提取结构化岗位要求。
- 从用户材料中检索相关证据。
- 生成带 evidence references 的求职内容。
- 评估 grounding、coverage、specificity 和 hallucination risk。
- 在 Web UI 中展示结果、证据和 warning。

## 非 MVP 范围

- 自动投递。
- 浏览器控制。
- 多用户登录。
- 支付系统。
- 社交功能。
- 复杂简历排版。

## 本地开发

MVP 阶段后端使用 `pip` 和 `requirements-dev.txt` 管理依赖。当前项目环境名为 `carrer_agent`。

```bash
conda activate carrer_agent
pip install -r requirements-dev.txt
pytest
uvicorn backend.app.main:app --reload
```

前端使用 Next.js：

```bash
cd frontend
npm install
npm run dev
```

### LLM Provider

后端默认使用 deterministic 本地 LLM client，方便 demo 和测试稳定运行。在这个模式下，不会调用真实大模型，所以不同 JD / 简历可能产生相似输出。

Web UI 也支持用户自己填写模型设置：可以选择 DeepSeek、OpenAI 或其他 OpenAI-compatible chat-completions 接口，输入自己的 API Key 后发起分析。首次提交后，这些设置会保存在用户自己的浏览器里，但 API Key 不会写死进项目文件。

如需使用真实 OpenAI 模型，请在启动后端前设置：

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4.1
conda run -n carrer_agent uvicorn backend.app.main:app --reload
```

如果请求里的 `run_config.model` 不是 `default`，它会覆盖 `OPENAI_MODEL`。

在未安装前端依赖前，可以先检查前端骨架：

```bash
cd frontend
npm run check
```

## 当前 API

- `GET /health` 返回 `{ "status": "ok" }`。
- `POST /analysis` 接收个人材料和岗位 JD，运行 workflow，并返回岗位要求、证据表、匹配分析、生成内容、评估报告和 warning。
