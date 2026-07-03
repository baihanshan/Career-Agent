# Numeric Claim Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Validate meaningful quantitative claims without treating dates, ordinals, model names, and list numbers as unsupported achievements.

**Architecture:** Deterministic extraction finds numeric candidates, typed classification assigns semantic roles, and deterministic comparison validates only claim types that require evidence.

**Tech Stack:** Python 3.11, regex, Pydantic v2, optional structured LLM classification, pytest.

---

状态：已完成

## 依赖

- `domain-models.md`
- `quality-gates.md`
- `docs/sprint2/fix_solution.md` 第 12 节

## 文件

- 新增：`backend/app/evaluation/numeric_claims.py`
- 修改：`backend/app/evaluation/evaluator.py`
- 新增：`backend/tests/test_numeric_claims.py`
- 修改：`backend/tests/test_evaluator.py`

## 最小任务

- [x] 编写失败测试：`17%`、AUC `0.957`、`3,242` 条语料被分类为需 grounding 的 claim。
- [x] 编写失败测试：`2025 年 1 月`、`第 4 条`、DeepLabV3+、Python 3 不生成成果数字风险。
- [x] 编写失败测试：`17%` 与 `0.17` 可按百分比语义规范化比较。
- [x] 编写失败测试：风险原因包含完整 claim 上下文，不只显示“数字 4”。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_numeric_claims.py`，确认失败。
- [x] 实现 `extract_numeric_claims(text)`、`classify_numeric_claim(candidate)`、`validate_numeric_claims(claims, evidence)`。
- [x] 只有 performance_metric、business_impact、dataset_size 和关键 count 进入严格证据比较。
- [x] 替换 evaluator 当前“所有数字集合差集”逻辑，并对规则/LLM重复 warning 去重。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_numeric_claims.py backend/tests/test_evaluator.py`。
- [x] 已生成提交命令：`git commit -m "fix: ground semantic numeric claims"`，由用户确认后执行。

## 验证记录

- RED：专项测试因 `numeric_claims` 模块不存在而收集失败，确认旧 evaluator 只有通用数字集合差集。
- GREEN：数字分类与 evaluator 专项测试全部通过；额外覆盖 duration 与 date 的语义区分。
- 回归：完整后端测试通过，规则 warning 与 LLM warning 可按声明去重。

## 完成标准

- 列表编号和日期不再产生高风险误报。
- 真正的量化成果仍严格要求证据。
- 数字风险对用户具有可解释上下文。
