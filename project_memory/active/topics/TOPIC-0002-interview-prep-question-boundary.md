---
id: TOPIC-0002
title: Interview Prep 区分 JD 岗位能力考察与简历深挖
status: active
level: P1
tags:
  - backend
  - interview-prep-agent
  - react-agent
  - prompt
  - question-generation
use_when: 修改 JD 相关面试问题、简历深挖问题、InterviewPrepAgent prompt 或面试问题质量门禁。
updated: 2026-07-02
---

# TOPIC-0002：Interview Prep 区分 JD 岗位能力考察与简历深挖

## 当前约定

`InterviewPrepAgent` 的两个问题列表职责不同：

- `jd_questions`：岗位能力考察型问题。基于 JD 的岗位方向、核心职责、必备技能、业务场景、技术栈、约束或能力要求生成，像真实面试官现场出的场景题、系统设计题、案例题或能力验证题。
- `resume_deep_dive_questions`：简历项目追问型问题。基于候选人的项目、实习、论文、比赛或经历，验证真实性、项目深度、个人贡献和技术细节。

JD 相关问题不应默认围绕简历项目展开，不应写成“在某项目中……”“结合你的项目……”或点名具体项目/公司/经历。回答也应优先围绕岗位场景给出方法、决策过程、权衡、验证方式和预期结果；简历 evidence 只能作为简短支撑或收尾关联，不应成为组织答案的主线。

## 实现位置

- `backend/app/workflow/interview_prep_agent.py`
  - `INTERVIEW_PREP_AGENT_PROMPT` 明确区分 `jd_questions` 与 `resume_deep_dive_questions` 的职责。
  - `_invocation_prompt` 增加 `question_generation_policy`，并向模型提供 requirement text、importance、capability_tags、logical_operator 和 alternatives，帮助模型从 JD 本身出岗位能力题。
  - `_validate_prep` 对 `jd_questions` 增加 `JD_QUESTION_USES_RESUME_EXPERIENCE` 门禁：若问题点名具体项目/公司/经历，要求改写为岗位能力场景题，并把项目追问放入 `resume_deep_dive_questions`。

## 验证

本次按用户要求未新增测试。已执行轻量语法检查：

```bash
python3 -m py_compile backend/app/workflow/interview_prep_agent.py
```

结果：通过。

