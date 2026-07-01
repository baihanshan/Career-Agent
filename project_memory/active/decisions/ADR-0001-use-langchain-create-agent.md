---
id: ADR-0001
title: ReAct Agent 工厂使用 langchain.agents.create_agent
status: active
level: P1
tags:
  - backend
  - langchain
  - react-agent
  - workflow
use_when: 修改 ResumeEvidenceAgent、InterviewPrepAgent、RiskAuditorAgent 或升级 LangChain/LangGraph Agent 运行时。
updated: 2026-06-30
---

# ADR-0001：ReAct Agent 工厂使用 langchain.agents.create_agent

## 决策

三个生产 ReAct Agent 工厂统一使用：

```python
from langchain.agents import create_agent
```

并通过 `create_agent(model=..., tools=..., system_prompt=..., response_format=..., name=...)` 创建 Agent。

不再在生产代码中使用旧入口：

```python
from langgraph.prebuilt import create_react_agent
```

## 范围

影响文件：

- `backend/app/workflow/resume_evidence_agent.py`
- `backend/app/workflow/interview_prep_agent.py`
- `backend/app/workflow/risk_auditor_agent.py`
- `backend/app/llm/react_model.py`
- `pyproject.toml`
- `requirements-dev.txt`

测试覆盖：

- `backend/tests/test_resume_evidence_agent.py`
- `backend/tests/test_interview_prep_agent.py`
- `backend/tests/test_risk_auditor_agent.py`
- `backend/tests/test_react_model.py`

## 原因

LangChain 当前 Agent 文档推荐使用 `langchain.agents.create_agent` 作为新入口。项目原实现使用 `langgraph.prebuilt.create_react_agent`，属于旧写法，会让后续升级和文档对齐成本变高。

## 实现约定

- 新依赖显式加入 `langchain>=1.0.0`。
- 移除项目对 `langgraph-prebuilt` 的直接依赖；`langchain/langgraph` 可自行拉取内部所需包。
- 新 API 使用 `system_prompt` 参数，不再使用旧 `prompt` 参数。
- 新 API 本身负责绑定 tools，Agent 工厂不要提前调用 `bind_react_tools`。
- 只有 OpenAI provider 使用 Pydantic `response_format`。
- DeepSeek 和 openai-compatible provider 不向 `create_agent` 传 Pydantic `BaseModel`；它们依赖 system prompt 中的显式 JSON 示例，以及项目自己的 fallback parser 解析最终 AI message。
- 这样做是因为 DeepSeek 官方主要承诺 JSON Object 模式与 function calling，而不是 LangChain Pydantic schema provider-native structured output。直接传 `BaseModel` 容易导致 `REACT_OUTPUT_PARSE_ERROR`。
- 测试 fake model 继续让最终 AI message 返回 JSON，并由项目自己的 fallback parser 解析，保持确定性测试稳定。

## 验证

已执行：

```bash
conda run -n carrer_agent pytest -q backend/tests/test_resume_evidence_agent.py backend/tests/test_interview_prep_agent.py backend/tests/test_risk_auditor_agent.py
conda run -n carrer_agent pytest -q backend/tests/test_react_model.py
env RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。完整后端测试通过时仅保留既有 `StarletteDeprecationWarning`。

## Evidence

- 生产代码搜索 `create_react_agent|langgraph.prebuilt|langgraph-prebuilt` 在 `backend`、`pyproject.toml`、`requirements-dev.txt` 中无结果。
- `backend/tests/test_resume_evidence_agent.py::test_factory_uses_langchain_create_agent`、`backend/tests/test_interview_prep_agent.py::test_factory_uses_langchain_create_agent`、`backend/tests/test_risk_auditor_agent.py::test_factory_uses_langchain_create_agent` 覆盖新工厂参数。
- `backend/tests/test_react_model.py::test_react_response_format_uses_schema_only_for_openai_provider_models` 覆盖 OpenAI、DeepSeek、openai-compatible 和 fake model 的 structured output 分流。
- 三个 Agent 测试均包含 `test_prompt_contains_explicit_json_example_for_json_mode_providers`，确保 system prompt 对 JSON-mode provider 有明确 JSON 示例。
