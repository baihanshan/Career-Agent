# CareerPilot Agent 总体进度

本文档跟踪 `docs/tasks/` 下各模块的完成情况。每个模块完成标准以对应任务文件中的 “完成标准” 为准。

## 模块进度

- [x] `project-setup.md`：项目骨架、开发命令和基础配置
- [x] `data-models.md`：核心 Pydantic/TypeScript 数据模型
- [x] `backend-api.md`：FastAPI health 与 analysis API
- [x] `document-processing.md`：文本标准化与 chunking
- [x] `retrieval.md`：embedding、Chroma indexing 与 evidence retrieval
- [x] `llm-service.md`：LLM client、prompt 与 structured output
- [x] `match-scoring.md`：岗位要求匹配评分
- [x] `writer.md`：简历 bullet、cover letter 与面试建议生成
- [x] `evaluator.md`：grounding、coverage、specificity 与 risk 检查
- [x] `workflow.md`：LangGraph 状态机与节点编排
- [x] `frontend.md`：输入、运行状态、结果和风险展示
- [x] `error-handling.md`：统一错误类型、API 错误响应和 warning 策略
- [x] `testing-fixtures.md`：样例 profile、JD、fake LLM、集成测试 fixture
- [ ] `deployment-docs.md`：Docker、README、demo walkthrough 与作品集说明

## 推荐执行顺序

1. `project-setup.md`
2. `data-models.md`
3. `backend-api.md`
4. `document-processing.md`
5. `retrieval.md`
6. `llm-service.md`
7. `match-scoring.md`
8. `writer.md`
9. `evaluator.md`
10. `workflow.md`
11. `frontend.md`
12. `error-handling.md`
13. `testing-fixtures.md`
14. `deployment-docs.md`

## MVP 完成检查

- [x] 用户可以输入个人材料和岗位 JD
- [x] 后端可以校验请求并返回结构化 response
- [x] 文档处理模块可以生成带 metadata 的 chunks
- [x] 检索模块可以返回带 source snippet 的 evidence
- [x] JD requirements 可以被结构化提取
- [x] match analysis 可以标记 strong、partial、weak、missing
- [x] 生成内容包含 evidence references
- [x] evaluator 可以标记 unsupported claims 和 coverage gaps
- [x] 前端可以展示结果、证据和风险提示
- [x] 核心模块有单元测试
- [x] 完整 workflow 有 fixture 集成测试
