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

- [ ] 创建 `backend/app/api/schemas.py`。
- [ ] 创建 `backend/app/documents/models.py`。
- [ ] 创建 `backend/app/workflow/state.py`。
- [ ] 创建 `backend/tests/test_schemas.py`。
- [ ] 为 `ProfileDocument` 写失败测试：空 `content` 应被拒绝。
- [ ] 实现 `ProfileDocument` Pydantic model。
- [ ] 运行 `pytest backend/tests/test_schemas.py`，确认 `ProfileDocument` 测试通过。
- [ ] 为 `ProfileDocument` 写失败测试：MVP 中 `pdf` 应返回暂不支持。
- [ ] 实现 `source_type` 校验，只允许 `text` 和 `markdown` 进入 MVP 流程。
- [ ] 为 `ProfileChunk` 写测试：必须包含 `chunk_id`、`document_id`、`source_name`、`text`。
- [ ] 实现 `ProfileChunk` model。
- [ ] 为 `JDRequirement` 写测试：`importance` 只允许 `high`、`medium`、`low`。
- [ ] 实现 `JDRequirement` model。
- [ ] 为 `EvidenceItem` 写测试：`score` 应在可比较的数值范围内。
- [ ] 实现 `EvidenceItem` model。
- [ ] 为 `MatchItem` 写测试：`match_level` 只允许 `strong`、`partial`、`weak`、`missing`。
- [ ] 实现 `MatchItem` model。
- [ ] 为 `GeneratedAssets` 写测试：resume bullet 必须包含 `evidence_ids` 字段。
- [ ] 实现 `ResumeBullet`、`CoverLetterDraft`、`InterviewPrepItem`、`GeneratedAssets`。
- [ ] 为 `EvaluationReport` 写测试：`overall_status` 只允许 `pass`、`pass_with_warnings`、`fail`。
- [ ] 实现 `GroundingWarning`、`CoverageGap`、`EvaluationReport`。
- [ ] 创建 `frontend/lib/types.ts`。
- [ ] 将 API response 相关类型同步到 `frontend/lib/types.ts`。
- [ ] 运行后端 schema 测试，确认全部通过。
