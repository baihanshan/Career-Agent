# Sprint 2 PDF 简历上传与纯文本结构识别任务

状态：已完成

## 目标

允许用户上传文字型 PDF 简历，将提取内容回填到可编辑文本框，并正确识别没有 Markdown 标记的项目、实习、教育、技能和奖项标题。

## 依赖

- `docs/proposal.md` 第 16 节
- `docs/detailed-design.md` 第 20 节
- `backend/app/api/routes.py`
- `backend/app/documents/parser.py`
- `backend/app/documents/chunker.py`
- `frontend/components/ProfileInput.tsx`
- `frontend/lib/api.ts`

## 完成标准

- 网页能够选择并上传单个文字型 PDF。
- 后端在内存中解析 PDF，不保存原文件。
- 解析成功后文本自动回填，用户可以继续编辑。
- 解析失败不会覆盖文本框原内容。
- 单个文件上限 10 MB。
- 扫描件或无文字 PDF 返回明确提示。
- 纯文本独立标题能生成正确的结构化 section。
- PDF 解析与现有分析 workflow 保持解耦。

## 最小任务清单

- [x] 在生产和开发依赖中加入 `pypdf` 与 FastAPI multipart 上传所需依赖。
- [x] 新增 PDF 解析 response schema 和受控错误码。
- [x] 新增 `backend/app/documents/pdf_parser.py`，实现逐页文字提取、页数统计和文本规范化。
- [x] 新增 `POST /documents/parse-pdf`，校验扩展名、内容类型、空文件和 10 MB 上限。
- [x] 处理加密 PDF、损坏 PDF 和无文字 PDF，并返回稳定错误码。
- [x] 为 PDF 解析器和上传 endpoint 编写先失败后通过的测试。
- [x] 扩展纯文本 chunking，使独立中文/英文简历标题能切换 section。
- [x] 为纯文本标题识别和正文误判保护编写先失败后通过的测试。
- [x] 在 `ProfileInput` 增加 PDF 文件选择、解析中状态、成功信息和错误信息。
- [x] 在前端 API 层新增 multipart PDF 上传函数。
- [x] 解析成功后回填文本并保留可编辑能力；分析请求使用 `source_type: "text"` 和原 PDF 文件名。
- [x] 确保解析失败时保留原文本，上传期间避免重复请求。
- [x] 更新前端结构检查，覆盖上传控件和用户友好错误文案。
- [x] 运行 PDF、文档处理、API 和 workflow 后端测试。
- [x] 运行前端 `npm run check` 与 `npm run build`。

## 验证记录

- 后端：`RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q`，169 项通过。
- 原始失败路径：纯文本中文标题测试与 `PDF_NO_TEXT` API 测试通过。
- 前端：`npm run check` 通过。
- 前端：`npm run build` 通过；存在既有的本地 SWC 原生模块加载警告，Next.js 自动回退后成功完成构建。

## 非目标

- OCR 或扫描件识别。
- 多 PDF 合并。
- PDF 永久存储。
- 拖拽上传。
- 解析成功后自动开始分析。
