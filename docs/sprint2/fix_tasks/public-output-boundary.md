# Public Output Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Separate internal traceable outputs from user-facing API models and guarantee that internal IDs never reach public text.

**Architecture:** Agents produce internal models containing evidence links. A deterministic projection creates public models and scans every user-visible field before `finalize_response`.

**Tech Stack:** Python 3.11, Pydantic v2, FastAPI schemas, pytest, TypeScript types.

---

状态：已完成

## 依赖

- `domain-models.md`
- `docs/sprint2/fix_solution.md` 第 11 节

## 文件

- 新增：`backend/app/workflow/public_output.py`
- 修改：`backend/app/api/schemas.py`
- 修改：`backend/app/workflow/state.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`frontend/lib/types.ts`
- 新增：`backend/tests/test_public_output.py`
- 修改：`backend/tests/test_observability.py`

## 最小任务

- [x] 编写失败测试：包含 `(evidence_ids: [...])`、`req_*`、`ev_*`、`chunk_*`、空 ID 数组的 public 文本被拒绝。
- [x] 编写失败测试：internal interview/risk/bullet 模型保留 evidence ID，但 public projection 不序列化这些字段。
- [x] 编写失败测试：正常技术名 `DeepLabV3+`、日期和百分比不会被 ID detector 误删。
- [x] 编写失败测试：`finalize_response` 只能序列化 public projection，不能直接 dump internal state。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_public_output.py`，确认失败。
- [x] 实现 `InternalIdLeakDetector`，扫描所有 public string field 并返回 field path。
- [x] 实现 `project_public_result(state)`，显式复制允许公开的字段。
- [x] 将泄露映射为 `INTERNAL_ID_LEAK` QualityIssue；静默清洗仅作为最终失败响应的日志兜底，不展示被污染文本。
- [x] 同步前端 types，确保 UI 不依赖内部 ID 字段。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_public_output.py backend/tests/test_observability.py backend/tests/test_api.py`。
- [x] 运行 `cd frontend && npm run check && npm run build`。
- [x] 已生成提交命令：`git commit -m "feat: isolate internal evidence from public output"`，由用户确认后执行。

## 验证记录

- RED：首次运行目标测试因 `backend.app.workflow.public_output` 不存在而收集失败。
- GREEN：public output、observability 与 API 测试共 27 项通过。
- 回归：完整后端测试共 229 项通过。
- 前端：`npm run check` 与 `npm run build` 通过。

## 完成标准

- Public API 文本中的内部 ID 泄露率为 0。
- 内部证据仍可用于校验和 trace。
- 前端无需负责清洗后端内部字段。
