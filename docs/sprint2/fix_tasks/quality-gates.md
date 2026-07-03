# Deterministic Quality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Build reusable deterministic validators for evidence allowlists, duplication, requirement restatement, snippet copying, answer relevance, and risk consistency.

**Architecture:** Each validator returns `QualityIssue` objects without mutating content. Agents receive retry feedback from issue codes; the workflow fails safely after three unsuccessful attempts.

**Tech Stack:** Python 3.11, Pydantic v2, existing embeddings/stdlib similarity, pytest.

---

状态：已完成

## 依赖

- `domain-models.md`
- `public-output-boundary.md`
- `docs/sprint2/fix_solution.md` 第 13 节

## 文件

- 新增：`backend/app/evaluation/quality_gate.py`
- 新增：`backend/tests/test_quality_gate.py`
- 修改：`backend/app/core/errors.py`

## 最小任务

- [x] 编写失败测试：未知、空白和跨分析 evidence ID 返回 `UNKNOWN_EVIDENCE_ID`。
- [x] 编写失败测试：“你如何满足岗位对……”返回 `QUESTION_RESTATES_REQUIREMENT`。
- [x] 编写失败测试：两个语义重复问题返回 `DUPLICATE_QUESTION`。
- [x] 编写失败测试：问题或答案连续复制过长 snippet 返回 `QUESTION_COPIES_SNIPPET` 或 `ANSWER_COPIES_SNIPPET`。
- [x] 编写失败测试：风险声称 missing 但 evidence selection 为 direct/strong 时返回 `RISK_CONTRADICTS_EVIDENCE`。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_quality_gate.py`，确认失败。
- [x] 实现 `PublicOutputQualityGate.validate_*` 系列纯函数，返回稳定、可排序的 QualityIssue 列表。
- [x] 使用明确阈值常量；复制率第一版用最长公共连续片段与长度比，不引入新依赖。
- [x] 实现 `quality_issues_to_retry_message()`，只提供失败字段和修正要求，不输出隐藏推理。
- [x] 增加 `REACT_QUALITY_GATE_FAILED` 和 `REACT_EVIDENCE_VIOLATION` 受控错误码。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_quality_gate.py backend/tests/test_error_handling.py`。
- [x] 已生成提交命令：`git commit -m "feat: add deterministic Agent quality gates"`，由用户确认后执行。

## 验证记录

- RED：首次运行目标测试因质量门禁模块和 ReAct 错误码不存在而收集失败。
- GREEN：质量门禁与错误处理测试共 13 项通过。
- 回归：完整后端测试共 236 项通过。

## 完成标准

- 所有 Agent 共用同一组安全规则。
- 质量失败能够生成精确重试反馈。
- 校验器可在无真实 LLM 环境下稳定测试。
