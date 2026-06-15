# Document Processing 模块任务

## 目标

实现用户材料的文本标准化和 chunking，使后续检索模块可以获得稳定、可追踪的 `ProfileChunk`。

## 依赖

- `data-models.md`

## 完成标准

- 支持 text 和 markdown 输入。
- Markdown heading 能生成 `section_label`。
- chunks 包含 source metadata。
- 空文本、过短文本、长文本都有明确行为。

## 最小任务清单

- [ ] 创建 `backend/app/documents/parser.py`。
- [ ] 创建 `backend/app/documents/chunker.py`。
- [ ] 创建 `backend/tests/test_document_processing.py`。
- [ ] 写测试：纯文本输入会去除首尾空白并统一换行。
- [ ] 实现 `normalize_text(content: str) -> str`。
- [ ] 运行文本标准化测试。
- [ ] 写测试：Markdown heading `## Projects` 会成为后续 chunk 的 `section_label`。
- [ ] 实现 Markdown section label 识别。
- [ ] 运行 Markdown section 测试。
- [ ] 写测试：空文档返回 processing warning 或 validation error。
- [ ] 实现空文档处理策略。
- [ ] 写测试：长段落会被切成多个 chunks。
- [ ] 实现基础 chunking，优先按 heading 和段落切分。
- [ ] 写测试：每个 chunk 包含 `chunk_id`、`document_id`、`source_name`、`text`。
- [ ] 实现 chunk metadata 填充。
- [ ] 写测试：chunk 输出顺序稳定。
- [ ] 确保 chunk id 生成方式稳定或可测试。
- [ ] 运行全部 document processing 测试。
