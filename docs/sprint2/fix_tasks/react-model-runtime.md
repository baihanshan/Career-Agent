# ReAct Model Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Provide a real tool-calling ChatModel runtime for OpenAI, DeepSeek, OpenAI-compatible providers, and deterministic tests.

**Architecture:** Keep the existing `LLMService` for one-shot structured generation. Add a separate `ReActModelFactory` that returns a LangChain-compatible ChatModel and rejects providers/models that cannot perform tool calling.

**Tech Stack:** Python 3.11, Pydantic v2, LangGraph, langchain-core, langchain-openai, pytest.

---

状态：已完成

## 依赖

- `docs/sprint2/fix_solution.md` 第 6 节
- 无前置修复模块

## 文件

- 修改：`pyproject.toml`
- 修改：`requirements-dev.txt`
- 新增：`backend/app/llm/react_model.py`
- 新增：`backend/tests/test_react_model.py`

## 最小任务

- [x] 在 `test_react_model.py` 编写失败测试：OpenAI、DeepSeek、OpenAI-compatible 配置分别生成正确 model、API key、base URL 和 temperature。
- [x] 编写失败测试：缺少 API key 或不支持 tool calling 时抛出 `ReActModelUnavailableError`，不得回退固定模板。
- [x] 编写失败测试：测试模式可注入 `FakeMessagesListChatModel`，且能够返回预设 tool call。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_react_model.py`，确认因模块不存在而失败。
- [x] 添加 `langchain-core`、`langchain-openai` 生产依赖并同步 `requirements-dev.txt`。
- [x] 实现 `ReActModelUnavailableError` 和 `ReActModelFactory.create(run_config)`；返回支持 `bind_tools` 的 ChatModel。
- [x] 为 DeepSeek/OpenAI-compatible 设置用户提供的 `base_url`；不得记录 API key。
- [x] 增加启动前 capability check，无法绑定工具时返回 `REACT_MODEL_UNAVAILABLE`。
- [x] 再次运行 `conda run -n carrer_agent pytest -q backend/tests/test_react_model.py`，确认全部通过。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_llm_service.py`，确认原有一次性 LLM 调用未回归。
- [x] 已生成提交命令：`git commit -m "feat: add tool-calling ReAct model runtime"`，由用户确认后执行。

## 验证记录

- RED：模块实现前运行目标测试，因 `backend.app.llm.react_model` 不存在而收集失败。
- GREEN：`backend/tests/test_react_model.py` 共 10 项测试通过。
- 回归：ReAct runtime 与原有 `LLMService` 合计 25 项测试通过。
- 生产加载冒烟：默认工厂成功创建 `ChatOpenAI`，未发起真实模型 API 请求。

## 完成标准

- 所有真实 ReAct Agent 获得统一 ChatModel。
- Provider 不支持工具调用时快速失败。
- 单元测试不访问真实模型 API。
