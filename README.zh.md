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

在未安装前端依赖前，可以先检查前端骨架：

```bash
cd frontend
npm run check
```

## 当前 API

- `GET /health` 返回 `{ "status": "ok" }`。
- `POST /analysis` 接收个人材料和岗位 JD，完成请求校验，并在完整 workflow 模块实现前返回 mock completed response。
