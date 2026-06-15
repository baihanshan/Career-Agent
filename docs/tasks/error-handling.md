# Error Handling 模块任务

## 目标

实现统一错误类型、API 错误响应和 warning 策略，让用户看到清楚、可恢复的信息，而不是内部异常。

## 依赖

- `backend-api.md`
- `workflow.md`

## 完成标准

- validation、document processing、vector store、LLM、workflow 错误有明确 code。
- warning 不阻断流程。
- error 阻断流程并返回用户可读 message。
- 前端能展示 API error 和 workflow warnings。

## 最小任务清单

- [x] 创建 `backend/app/core/errors.py`。
- [x] 定义 `ValidationErrorCode`、`DocumentProcessingErrorCode`、`VectorStoreErrorCode`、`LLMErrorCode`、`WorkflowErrorCode`。
- [x] 创建统一 `AppError` model。
- [x] 写测试：validation error 返回可读 message。
- [x] 在 API 层接入 validation error formatting。
- [x] 写测试：vector store failure 返回 `VECTOR_STORE_ERROR`。
- [x] 在 workflow service 中捕获 vector store error。
- [x] 写测试：LLM parser error 重试后仍失败返回 `LLM_OUTPUT_PARSE_ERROR`。
- [x] 在 workflow 中实现 LLM parse retry 状态。
- [x] 定义 `ProcessingWarning` model。
- [x] 写测试：用户材料过短时生成 warning 但不中断。
- [x] 在 document processing 中返回 warning。
- [x] 写测试：weak evidence 进入 evaluation report 而不是 API error。
- [x] 在 API response 中保留 warnings。
- [x] 前端添加 error display。
- [x] 前端添加 warning display。
- [x] 运行 `pytest backend/tests/test_error_handling.py backend/tests/test_workflow_integration.py`，确认错误响应和 workflow error path 测试通过。
