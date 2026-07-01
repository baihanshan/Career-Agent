# 项目记忆索引

更新日期：2026-07-01

本文件是有限的记忆路由层。不要在这里放入过长的记忆内容。

## 活跃条目

<!-- 活跃条目保持在 50 条以内。当前活跃条目：3。 -->

- id: ADR-0001-use-langchain-create-agent
  path: project_memory/active/decisions/ADR-0001-use-langchain-create-agent.md
  title: ReAct Agent 工厂使用 langchain.agents.create_agent
  level: P1
  status: active
  tags: 
  use_when: 修改 ResumeEvidenceAgent、InterviewPrepAgent、RiskAuditorAgent 或升级 LangChain/LangGraph Agent 运行时。

- id: BUG-0001-resume-evidence-recursion-limit
  path: project_memory/active/bugs/BUG-0001-resume-evidence-recursion-limit.md
  title: DeepSeek resume_evidence_agent hits LangGraph recursion limit
  level: P1
  status: active
  tags:
    - backend
    - deepseek
    - react-agent
    - resume-evidence-agent
    - langgraph
  use_when: Debugging `/analysis` failures where DeepSeek ReAct agents loop on tools, hit `GraphRecursionError`, or return `REACT_RECURSION_LIMIT_ERROR` / `REACT_OUTPUT_PARSE_ERROR`.

- id: BUG-0002-interview-prep-evidence-id-normalization
  path: project_memory/active/bugs/BUG-0002-interview-prep-evidence-id-normalization.md
  title: DeepSeek interview_prep_agent emits unstable supporting evidence IDs
  level: P1
  status: active
  tags:
    - backend
    - deepseek
    - react-agent
    - interview-prep-agent
    - evidence-allowlist
  use_when: Debugging `/analysis` failures where frontend shows invalid evidence, backend returns `REACT_EVIDENCE_VIOLATION`, or `interview_prep_agent` fails at `quality_gate`.


## 置顶条目

<!-- 置顶条目保持在 10 条以内。 -->

## 最近条目

<!-- 最近条目保持在 15 条以内。 -->
