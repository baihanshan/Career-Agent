# Quality Regression and Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Convert every `fix_problem.md` example into automated regressions and a repeatable human quality review.

**Architecture:** Use sanitized representative resume/JD fixtures, deterministic Fake ChatModel tool-call fixtures, semantic assertions, and an explicit manual scorecard. Tests assert behaviors rather than exact LLM prose.

**Tech Stack:** pytest, FastAPI TestClient, Fake ChatModel, JSON/Markdown fixtures, Next.js structure checks.

---

状态：已完成（主观人工评分待评审人执行）

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

- [x] 创建去标识化 fixture，保留语义分割、NLP 分类、RAG、多模态实习、Python 技术栈和量化成果等关键事实。
- [x] 编写回归测试：qualification 不生成 JD 技术问题。
- [x] 编写回归测试：Python/算法和多模态要求生成带场景、约束、权衡的专业问题。
- [x] 编写回归测试：项目问题不复制整段简历，答案复制率低于门禁阈值。
- [x] 编写回归测试：Python、CV/ML、NLP、RAG、多模态的 evidence support 判断正确。
- [x] 编写回归测试：OR requirement 满足任一分支即覆盖。
- [x] 编写回归测试：列表编号 4、日期、DeepLabV3+ 不生成 unsupported metric 风险。
- [x] 编写回归测试：所有 public text 的 internal ID leakage rate 为 0，unknown evidence rate 为 0。
- [x] 编写前端结构检查：UI 不读取或渲染 internal evidence/requirement/chunk fields。
- [x] 运行 `env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_fix_solution_regressions.py`。
- [x] 运行完整后端：`env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q`。
- [x] 运行完整前端：`cd frontend && npm run check && npm run build`。
- [x] 创建人工 QA checklist，评分问题专业性、相关性、答案自然度/针对性、风险准确性和建议可执行性。
- [x] 记录完整测试数、前端命令和人工 QA 结果到本任务文档。
- [x] 已生成提交命令：`git commit -m "test: add Sprint 2 quality regression suite"`，由用户确认后执行。

## 验证记录

- RED：新增回归首次运行 7 项因三个质量 fixture 尚不存在而失败，数字分类用例已通过。
- 目标回归：`8 passed`。
- 完整后端：`285 passed`；另有 102 条既有依赖弃用警告，不影响测试结果。
- 前端结构检查：`npm run check` 通过，且会递归检查 `app/` 与 `components/` 不读取或渲染内部引用字段。
- 前端生产构建：`npm run build` 通过。当前环境的原生 SWC 文件加载失败后自动使用后备实现，构建、类型检查与静态页面生成均成功。
- 人工 QA：已生成可重复评分表；主观评分待产品或人工评审人使用真实模型执行，未用自动化结果代替人工结论。

## 完成标准

- `fix_problem.md` 的每类问题都有自动化回归。
- 测试不要求 LLM 逐字输出固定答案。
- 人工质量评审可以重复执行并比较版本差异。
