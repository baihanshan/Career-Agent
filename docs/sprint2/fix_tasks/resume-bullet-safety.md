# Resume Bullet Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Keep LLM-generated resume bullets evidence-grounded while guaranteeing that IDs and unsupported facts never enter user-visible text.

**Architecture:** Resume Bullet remains a one-shot structured LLM node. It consumes semantic `EvidenceSelection` results, produces internal bullets, then passes allowlist and public-output gates.

**Tech Stack:** Existing LLMService, Pydantic v2, deterministic quality gates, pytest.

---

状态：待实现

## 依赖

- `resume-evidence-react-agent.md`
- `public-output-boundary.md`
- `quality-gates.md`
- `docs/sprint2/fix_solution.md` 第 3.1、11 节

## 文件

- 修改：`backend/app/llm/prompts.py`
- 修改：`backend/app/llm/structured_outputs.py`
- 修改：`backend/app/workflow/writer.py`
- 修改：`backend/tests/test_writer.py`
- 修改：`backend/tests/test_llm_service.py`

## 最小任务

- [ ] 编写失败测试：bullet text 中出现 `(evidence_ids: [...])`、空 ID 或 `req_*` 时输出被拒绝。
- [ ] 编写失败测试：structured `evidence_ids` 保留在 internal bullet，public bullet 只展示自然语言。
- [ ] 编写失败测试：bullet 只能引用 EvidenceSelection/allowlist 中的证据。
- [ ] 编写失败测试：仅有 skill contextual support 时不得生成夸大的实践成果。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_writer.py -k "evidence or public or id"`，确认失败。
- [ ] 更新 Prompt，明确 ID 只能位于 JSON internal field，绝不进入 text。
- [ ] 更新 structured output normalization，禁止从自然语言中接受或回填 ID 注释。
- [ ] 在 writer 返回前执行 evidence allowlist 与 ID leakage gate；不合格结果触发一次 structured regeneration，仍失败则返回受控错误。
- [ ] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_writer.py backend/tests/test_llm_service.py backend/tests/test_public_output.py`。
- [ ] 提交：`git commit -m "fix: enforce safe evidence-grounded resume bullets"`。

## 完成标准

- 三条 bullet 均可追踪但不展示内部 ID。
- 未知或空 evidence ID 不进入最终结果。
- Prompt 失败时仍有确定性保护。

