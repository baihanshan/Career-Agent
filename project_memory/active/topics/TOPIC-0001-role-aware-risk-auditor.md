---
id: TOPIC-0001
title: Risk Auditor 使用岗位类型感知的核心风险优先级
status: active
level: P1
tags:
  - backend
  - risk-auditor-agent
  - react-agent
  - prompt
  - screening-risk
use_when: 修改风险提示、RiskAuditorAgent prompt、risk ranking、JD/简历匹配风险优先级，或调试泛软技能风险过多的问题。
updated: 2026-07-01
---

# TOPIC-0001：Risk Auditor 使用岗位类型感知的核心风险优先级

## 背景

用户真实复测后发现 `/analysis` 已跑通，但风险提示容易输出泛泛的软技能问题，例如“学习能力与适应性缺少具体例证”“沟通与团队协同能力缺少直接例证”。这些可能是 JD 文字要求，但通常不是技术研发或产品/项目管理岗位的核心筛选风险。

## 当前约定

Risk Auditor 不应机械逐条匹配 JD。它必须先判断岗位类型，再识别该岗位真正影响初筛或面试通过率的核心风险。

技术研发类岗位优先级：

```text
core_technical_direction
missing_required_technology
algorithm_model_system_architecture
project_depth
engineering_implementation
data_modeling
scale_distributed_deployment_stability
quantified_outcomes
generic_soft_skill
```

产品/项目管理类岗位优先级：

```text
requirement_analysis
business_user_scenario_understanding
product_project_ownership
zero_to_one_or_scale_delivery
cross_functional_delivery
business_outcome_metrics
personal_contribution_clarity
generic_soft_skill
```

软技能默认低优先级。只有当软技能是该岗位真实核心筛选项、简历无法通过项目/实习/团队交付/成果间接证明，并且该缺口会实际影响筛选或面试时，才应输出为风险。

## 实现位置

- `backend/app/workflow/risk_auditor_agent.py`
  - `RISK_AUDITOR_AGENT_PROMPT` 要求先判断 role type，再按岗位核心维度筛风险。
  - `_invocation_prompt` 向模型提供 `risk_audit_policy`、JD excerpt、requirement text/category/capability tags 等内部上下文。
  - `InternalRiskItem` 支持内部 `risk_dimension` 和 `risk_priority`，public projection 不输出这些字段。
  - `_normalize_internal_supporting_evidence_ids` 在质量门禁前过滤未知 `internal_supporting_evidence_ids`，并按 risk 的 `requirement_ids` 回填同 requirement 且本轮工具已 allowlist 的真实 evidence id。
  - `_parse_final_report` 通过 `_coerce_risk_report_payload` 兼容 DeepSeek 真实输出形态，包括 `risk_report.risks` 包装、裸 risks 数组、中文 severity、字符串 priority、字符串 requirement/evidence id。
- `backend/app/workflow/react_tools.py`
  - `rank_candidate_risks` 按 severity、risk_priority、risk_dimension 排序，避免泛软技能压过核心技术/项目/业务风险。

## 验证

已执行：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_risk_auditor_agent.py
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_interview_prep_agent.py backend/tests/test_risk_auditor_agent.py backend/tests/test_public_output.py
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。完整后端测试仅保留既有 `StarletteDeprecationWarning`。
