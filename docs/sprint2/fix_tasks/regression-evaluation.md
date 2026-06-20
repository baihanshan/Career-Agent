# Quality Regression and Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Convert every `fix_problem.md` example into automated regressions and a repeatable human quality review.

**Architecture:** Use sanitized representative resume/JD fixtures, deterministic Fake ChatModel tool-call fixtures, semantic assertions, and an explicit manual scorecard. Tests assert behaviors rather than exact LLM prose.

**Tech Stack:** pytest, FastAPI TestClient, Fake ChatModel, JSON/Markdown fixtures, Next.js structure checks.

---

状态：待实现

## 依赖

- `workflow-integration.md`
- 所有前序 fix modules
- `docs/sprint2/fix_solution.md` 第 16、20 节

## 文件

- 新增：`backend/tests/fixtures/fix_quality_profile.md`
- 新增：`backend/tests/fixtures/fix_quality_jd.txt`
- 新增：`backend/tests/fixtures/fix_react_tool_calls.json`
- 新增：`backend/tests/test_fix_solution_regressions.py`
- 新增：`docs/sprint2/fix_tasks/qa-checklist.md`
- 修改：`frontend/scripts/verify-structure.mjs`

## 最小任务

- [ ] 创建去标识化 fixture，保留语义分割、NLP 分类、RAG、多模态实习、Python 技术栈和量化成果等关键事实。
- [ ] 编写回归测试：qualification 不生成 JD 技术问题。
- [ ] 编写回归测试：Python/算法和多模态要求生成带场景、约束、权衡的专业问题。
- [ ] 编写回归测试：项目问题不复制整段简历，答案复制率低于门禁阈值。
- [ ] 编写回归测试：Python、CV/ML、NLP、RAG、多模态的 evidence support 判断正确。
- [ ] 编写回归测试：OR requirement 满足任一分支即覆盖。
- [ ] 编写回归测试：列表编号 4、日期、DeepLabV3+ 不生成 unsupported metric 风险。
- [ ] 编写回归测试：所有 public text 的 internal ID leakage rate 为 0，unknown evidence rate 为 0。
- [ ] 编写前端结构检查：UI 不读取或渲染 internal evidence/requirement/chunk fields。
- [ ] 运行 `env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_fix_solution_regressions.py`。
- [ ] 运行完整后端：`env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q`。
- [ ] 运行完整前端：`cd frontend && npm run check && npm run build`。
- [ ] 创建人工 QA checklist，评分问题专业性、相关性、答案自然度/针对性、风险准确性和建议可执行性。
- [ ] 记录完整测试数、前端命令和人工 QA 结果到本任务文档。
- [ ] 提交：`git commit -m "test: add Sprint 2 quality regression suite"`。

## 完成标准

- `fix_problem.md` 的每类问题都有自动化回归。
- 测试不要求 LLM 逐字输出固定答案。
- 人工质量评审可以重复执行并比较版本差异。

