# Project Memory Index

Updated: 2026-07-02

This file is a bounded routing layer. Do not put long memory content here.

## Active Entries

<!-- Keep active entries <= 50. Current active entries: 5. -->

- id: BUG-0001-resume-evidence-recursion-limit
  path: project_memory/active/bugs/BUG-0001-resume-evidence-recursion-limit.md
  title: DeepSeek resume_evidence_agent hits LangGraph recursion limit
  level: P1
  status: active
  tags: 
  use_when: Debugging `/analysis` failures where DeepSeek ReAct agents loop on tools, hit `GraphRecursionError`, or return `REACT_RECURSION_LIMIT_ERROR` / `REACT_OUTPUT_PARSE_ERROR`.

- id: BUG-0002-interview-prep-evidence-id-normalization
  path: project_memory/active/bugs/BUG-0002-interview-prep-evidence-id-normalization.md
  title: DeepSeek interview_prep_agent emits unstable supporting evidence IDs
  level: P1
  status: active
  tags: 
  use_when: Debugging `/analysis` failures where frontend shows invalid evidence, backend returns `REACT_EVIDENCE_VIOLATION`, or `interview_prep_agent` fails at `quality_gate`.

- id: ADR-0001-use-langchain-create-agent
  path: project_memory/active/decisions/ADR-0001-use-langchain-create-agent.md
  title: ReAct Agent 工厂使用 langchain.agents.create_agent
  level: P1
  status: active
  tags: 
  use_when: 修改 ResumeEvidenceAgent、InterviewPrepAgent、RiskAuditorAgent 或升级 LangChain/LangGraph Agent 运行时。

- id: TOPIC-0001-role-aware-risk-auditor
  path: project_memory/active/topics/TOPIC-0001-role-aware-risk-auditor.md
  title: Risk Auditor 使用岗位类型感知的核心风险优先级
  level: P1
  status: active
  tags: 
  use_when: 修改风险提示、RiskAuditorAgent prompt、risk ranking、JD/简历匹配风险优先级，或调试泛软技能风险过多的问题。

- id: TOPIC-0002-interview-prep-question-boundary
  path: project_memory/active/topics/TOPIC-0002-interview-prep-question-boundary.md
  title: Interview Prep 区分 JD 岗位能力考察与简历深挖
  level: P1
  status: active
  tags: 
  use_when: 修改 JD 相关面试问题、简历深挖问题、InterviewPrepAgent prompt 或面试问题质量门禁。


## Pinned Entries

<!-- Keep pinned entries <= 10. -->

## Recent Entries

<!-- Keep recent entries <= 15. -->
