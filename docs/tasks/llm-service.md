# LLM Service 模块任务

## 目标

封装模型调用、prompt 模板和 structured output 解析，让 workflow 节点不直接依赖具体 LLM provider。

## 依赖

- `data-models.md`

## 完成标准

- 有 fake LLM client 支持稳定测试。
- JD extraction、application generation、grounding evaluation 都通过明确接口暴露。
- LLM 输出解析失败能被识别。

## 最小任务清单

- [x] 创建 `backend/app/llm/client.py`。
- [x] 创建 `backend/app/llm/prompts.py`。
- [x] 创建 `backend/app/llm/structured_outputs.py`。
- [x] 创建 `backend/tests/test_llm_service.py`。
- [x] 定义 `LLMClient` interface。
- [x] 实现 `FakeLLMClient`，根据输入 key 返回固定 JSON。
- [x] 写测试：fake client 对 sample JD 返回固定 requirements JSON。
- [x] 实现 `extract_jd_requirements(job_description)`。
- [x] 写测试：malformed requirements JSON 触发 parse error。
- [x] 实现 structured output parser。
- [x] 写测试：application assets JSON 能解析为 `GeneratedAssets`。
- [x] 实现 `generate_application_assets(context)` 接口。
- [x] 写测试：grounding warnings JSON 能解析为 `EvaluationReport` 或 warning list。
- [x] 实现 `evaluate_claim_grounding(claims, evidence_items)` 接口。
- [x] 将 prompts 写入 `prompts.py`，明确禁止编造经历。
- [x] 运行 LLM service 测试。
