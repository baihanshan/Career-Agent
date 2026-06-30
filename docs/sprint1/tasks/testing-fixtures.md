# Testing Fixtures 模块任务

## 目标

建立稳定的 sample profile、sample JD、fake LLM response 和集成测试 fixture，使核心 workflow 可以不依赖真实模型稳定运行。

## 依赖

- `data-models.md`
- `llm-service.md`
- `workflow.md`

## 完成标准

- 有一份小型 sample profile。
- 有一份小型 sample JD。
- 有 fake LLM outputs。
- 集成测试可以使用 fixture 跑完整 workflow。

## 最小任务清单

- [x] 创建 `backend/tests/fixtures/sample_profile.md`。
- [x] 在 sample profile 中包含教育背景、AI 课程项目、技能和 GitHub 项目描述。
- [x] 创建 `backend/tests/fixtures/sample_jd.txt`。
- [x] 在 sample JD 中包含 hard skills、responsibilities、nice-to-have。
- [x] 创建 `backend/tests/fixtures/fake_llm_jd_requirements.json`。
- [x] 创建 `backend/tests/fixtures/fake_llm_generated_assets.json`。
- [x] 创建 `backend/tests/fixtures/fake_llm_evaluation.json`。
- [x] 写 fixture loader helper。
- [x] 写测试：sample profile 可以被 document processing 切分。
- [x] 写测试：sample JD 可以被 fake LLM 解析为 requirements。
- [x] 写测试：fake generated assets 符合 schema。
- [x] 写测试：完整 workflow fixture 产生至少一个 evidence item。
- [x] 写测试：完整 workflow fixture 产生至少一个 resume bullet。
- [x] 写测试：完整 workflow fixture 产生 evaluation report。
- [x] 在 README 中说明 fixture 的用途。
