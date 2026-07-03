# Sprint 2 Structured Resume Processing 任务

状态：已完成

## 目标

将简历材料从普通文本 chunk 升级为结构化 section + metadata + chunk，使检索能够优先使用项目和实习，而不是技能列表。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/documents/parser.py`
- `backend/app/documents/chunker.py`
- `backend/app/documents/models.py`

## 完成标准

- 简历内容能被识别为 project、internship、skill、education、other。
- 每个 chunk 带 section metadata。
- 项目和实习 metadata 支持公司名、岗位名、项目名、技术栈。
- 技能列表不再作为简历要点主来源，只作为辅助证据。

## 最小任务清单

- [x] 为 `ProfileChunk` 增加 `section_type` metadata。
- [x] 为 `ProfileChunk` 增加 `section_title`、`company_name`、`role_title`、`project_name`、`technologies` metadata。
- [x] 实现 Markdown heading 到 section_type 的规则映射。
- [x] 实现中文 heading 识别：实习经历、项目经历、技能、教育背景、其他。
- [x] 实现英文 heading 识别：Internship、Experience、Projects、Skills、Education、Other。
- [x] 将 project 和 internship chunk 的内容保留得更完整，避免切碎关键上下文。
- [x] 为 skill section 打标，但降低后续检索和生成优先级。
- [x] 编写测试：项目经历能被识别为 `project`。
- [x] 编写测试：实习经历能被识别为 `internship`。
- [x] 编写测试：技能列表不会被误判为项目或实习。
