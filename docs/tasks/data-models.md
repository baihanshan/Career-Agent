# Data Models 模块任务

## 目标

实现详细设计中的核心数据模型，为 API、workflow、检索、生成和评估提供一致的数据契约。

## 依赖

- `project-setup.md`

## 完成标准

- 后端 Pydantic models 覆盖 detailed-design 中的核心字段。
- 前端 TypeScript types 与 API response 的关键结构一致。
- 模型校验测试覆盖空输入、不支持文件类型、risk level、match level 等关键枚举。

## 最小任务清单

- [x] 创建 `backend/app/api/schemas.py`。
- [x] 创建 `backend/app/documents/models.py`。
- [x] 创建 `backend/app/workflow/state.py`。
- [x] 创建 `backend/tests/test_schemas.py`。
- [x] 为 `ProfileDocument` 写失败测试：空 `content` 应被拒绝。
- [x] 实现 `ProfileDocument` Pydantic model。
- [x] 运行 `pytest backend/tests/test_schemas.py`，确认 `ProfileDocument` 测试通过。
- [x] 为 `ProfileDocument` 写失败测试：MVP 中 `pdf` 应返回暂不支持。
- [x] 实现 `source_type` 校验，只允许 `text` 和 `markdown` 进入 MVP 流程。
- [x] 为 `ProfileChunk` 写测试：必须包含 `chunk_id`、`document_id`、`source_name`、`text`。
- [x] 实现 `ProfileChunk` model。
- [x] 为 `JDRequirement` 写测试：`importance` 只允许 `high`、`medium`、`low`。
- [x] 实现 `JDRequirement` model。
- [x] 为 `EvidenceItem` 写测试：`score` 应在可比较的数值范围内。
- [x] 实现 `EvidenceItem` model。
- [x] 为 `MatchItem` 写测试：`match_level` 只允许 `strong`、`partial`、`weak`、`missing`。
- [x] 实现 `MatchItem` model。
- [x] 为 `GeneratedAssets` 写测试：resume bullet 必须包含 `evidence_ids` 字段。
- [x] 实现 `ResumeBullet`、`CoverLetterDraft`、`InterviewPrepItem`、`GeneratedAssets`。
- [x] 为 `EvaluationReport` 写测试：`overall_status` 只允许 `pass`、`pass_with_warnings`、`fail`。
- [x] 实现 `GroundingWarning`、`CoverageGap`、`EvaluationReport`。
- [x] 创建 `frontend/lib/types.ts`。
- [x] 将 API response 相关类型同步到 `frontend/lib/types.ts`。
- [x] 运行后端 schema 测试，确认全部通过。
