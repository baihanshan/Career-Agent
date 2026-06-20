# JD Requirement Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Classify each JD requirement by capability, verification mode, interviewability, and question focus.

**Architecture:** Extend structured JD extraction rather than deriving interview behavior from raw requirement text later. Keep backward-compatible defaults in the parser for providers that omit optional fields.

**Tech Stack:** Python 3.11, Pydantic v2, existing LLMService, structured JSON, pytest.

---

状态：已完成

## 依赖

- `domain-models.md`
- `docs/sprint2/fix_solution.md` 第 7.2、9.2 节

## 文件

- 修改：`backend/app/api/schemas.py`
- 修改：`backend/app/llm/prompts.py`
- 修改：`backend/app/llm/structured_outputs.py`
- 修改：`backend/tests/test_llm_service.py`
- 修改：`backend/tests/test_schemas.py`

## 最小任务

- [x] 编写失败测试：计算机硕士/博士要求被标为 `document_check` 且 `interviewability=false`。
- [x] 编写失败测试：Python/算法要求被标为 `technical_question`，包含 programming、algorithms capability tags。
- [x] 编写失败测试：多模态平台职责被标为 `system_design` 并给出 platform/design/evaluation question focus。
- [x] 编写失败测试：“NLP/多模态至少一个领域”保留 OR 逻辑分支，不能扁平化成全部必需。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_llm_service.py -k requirement`，确认失败。
- [x] 扩展 `JDRequirement`：`capability_tags`、`verification_mode`、`interviewability`、`question_focus`、`logical_operator`、`alternatives`。
- [x] 更新 JD Prompt，要求模型区分 document check、evidence check、technical question、system design 和 behavioral question。
- [x] 更新 `_normalize_jd_requirement`，为旧响应提供安全默认值，不把 qualification 默认设为可面试。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_llm_service.py backend/tests/test_schemas.py`，确认通过。
- [x] 已生成提交命令：`git commit -m "feat: classify JD requirement semantics"`，由用户确认后执行。

## 验证记录

- RED：语义字段不存在，且 schema 未拒绝缺少 focus 或无有效分支的矛盾状态。
- GREEN：LLM service 与 schema 测试共 39 项通过。
- 回归：完整后端测试共 213 项通过。

## 完成标准

- 静态资格要求不会进入技术面试题生成。
- OR 条件在后续 evidence/risk 判断中可被准确消费。
- 每条可面试要求都有明确 question focus。
