# Experience Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute every checkbox in order and use TDD for production changes.

**Goal:** Split project and internship sections into individual `ExperienceRecord` objects so Agents no longer consume whole resume sections.

**Architecture:** Reuse deterministic section heading detection, then split each project/internship section by experience header and date patterns. Preserve raw chunk IDs and original text; never infer facts that are absent.

**Tech Stack:** Python 3.11, regex, Pydantic v2, pytest.

---

状态：已完成

## 依赖

- `domain-models.md`
- `docs/sprint2/fix_solution.md` 第 7.1 节

## 文件

- 新增：`backend/app/documents/experience_parser.py`
- 修改：`backend/app/documents/chunker.py`
- 修改：`backend/app/workflow/nodes.py`
- 修改：`backend/app/workflow/state.py`
- 新增：`backend/tests/test_experience_parser.py`
- 修改：`backend/tests/test_document_processing.py`

## 最小任务

- [x] 将 `fix_problem.md` 使用的三个项目和腾讯实习整理为测试 fixture，不添加原文不存在的字段。
- [x] 编写失败测试：三个连续项目被拆为三个 `ExperienceRecord`，而不是一个 800 字符大 chunk。
- [x] 编写失败测试：腾讯实习提取 company、role、date range、responsibilities、technologies 和 outcomes。
- [x] 编写失败测试：缺少明确项目名时生成稳定 fallback name，但保留完整 raw text 和 source chunk ID。
- [x] 编写失败测试：同一经历的多行内容不会被拆成多个 ExperienceRecord。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_experience_parser.py`，确认失败。
- [x] 实现 `parse_experience_records(document, chunks)`，只做抽取与切分，不改写事实。
- [x] 在 `index_profile` 中写入 `state.experience_records`，同时保留原有 `profile_chunks` 供检索兼容。
- [x] 调整 project/internship chunk，使每个 ExperienceRecord 形成独立检索单元。
- [x] 运行 `conda run -n carrer_agent pytest -q backend/tests/test_experience_parser.py backend/tests/test_document_processing.py backend/tests/test_retrieval.py`，确认通过。
- [x] 已生成提交命令：`git commit -m "feat: structure individual resume experiences"`，由用户确认后执行。

## 验证记录

- RED：首次运行目标测试因 `backend.app.documents.experience_parser` 不存在而收集失败。
- GREEN：parser、document processing 与 retrieval 目标测试共 31 项通过。
- 回归：完整后端测试共 207 项通过。

## 完成标准

- 每个项目和实习都有稳定 `experience_id`。
- Agent 不需要在问题中引用整段 section 来定位经历。
- 原始文本保持可追溯且不被补造。
