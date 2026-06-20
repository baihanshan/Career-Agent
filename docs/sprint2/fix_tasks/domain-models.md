# ReAct Domain Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Introduce explicit experience, requirement semantics, evidence support, numeric claim, quality issue, and internal Agent result models.

**Architecture:** Put workflow-only models in a dedicated internal module while keeping API-facing schemas stable. Use enums and Pydantic validators to prevent contradictory states before Agent output enters the workflow.

**Tech Stack:** Python 3.11, Pydantic v2, pytest.

---

状态：待实现

## 依赖

- `docs/sprint2/fix_solution.md` 第 7、11、12、13 节
- 无前置修复模块

## 文件

- 新增：`backend/app/workflow/domain_models.py`
- 修改：`backend/app/workflow/state.py`
- 新增：`backend/tests/test_fix_domain_models.py`

## 最小任务

- [ ] 编写失败测试：`ExperienceRecord` 接受 project/internship、名称、职责、技术、难点、行动、结果、指标和原始 chunk ID。
- [ ] 编写失败测试：`EvidenceSelection` 的 strong/partial 结果必须包含证据，missing 结果不得声明 direct support。
- [ ] 编写失败测试：`NumericClaim` 只接受 `performance_metric`、`business_impact`、`dataset_size`、`count`、`date`、`duration`、`ordinal`、`model_or_version`、`other`。
- [ ] 编写失败测试：`QualityIssue` 必须包含 code、field_path、message、retry_instruction 和 severity。
- [ ] 编写失败测试：internal interview/risk 模型保留 ID 字段，public 文本字段不能为空。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_fix_domain_models.py`，确认因模型不存在而失败。
- [ ] 实现 `VerificationMode`、`SupportType`、`NumericClaimType` 和对应 Pydantic models。
- [ ] 在 `WorkflowState` 增加 `experience_records`、`evidence_selections`、`allowed_evidence_ids` 和 `quality_issues`，全部使用空集合默认值。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_fix_domain_models.py backend/tests/test_schemas.py`，确认通过。
- [ ] 提交：`git commit -m "feat: add structured ReAct domain models"`。

## 完成标准

- Agent 内部推理数据不再依赖任意 dict。
- 矛盾的证据支持状态会被 Pydantic 拒绝。
- 新字段不会破坏现有 API schema。

