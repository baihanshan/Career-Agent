# Backend API 模块任务

## 目标

实现 FastAPI 的最小 API 层：健康检查、analysis 请求校验、workflow 调用和结构化响应。

## 依赖

- `project-setup.md`
- `data-models.md`

## 完成标准

- `GET /health` 返回 `{ "status": "ok" }`。
- `POST /analysis` 能接收合法请求并调用 workflow service。
- 无效请求返回明确 validation error。
- API 测试覆盖成功和失败路径。

## 最小任务清单

- [x] 创建 `backend/app/api/routes.py`。
- [x] 创建 `backend/app/api/__init__.py`。
- [x] 在 `backend/app/main.py` 创建 FastAPI app。
- [x] 写 `GET /health` 的失败测试。
- [x] 实现 `GET /health`。
- [x] 运行 health endpoint 测试，确认通过。
- [x] 定义 `AnalysisRequest` schema。
- [x] 定义 `AnalysisResponse` schema。
- [x] 写测试：空 `profile_documents` 调用 `/analysis` 应返回 422。
- [x] 写测试：空 `job_description` 调用 `/analysis` 应返回 422。
- [x] 写测试：`source_type: "pdf"` 调用 `/analysis` 应返回 422 或明确 unsupported error。
- [x] 创建 `backend/app/workflow/service.py`，提供 `run_analysis(request)` 占位函数。
- [x] 写测试：合法 `/analysis` 请求会调用 workflow service。
- [x] 实现 `/analysis` endpoint，先返回 mock completed response。
- [x] 将 API routes 注册到 FastAPI app。
- [x] 运行 API 测试，确认通过。
- [x] 在 README 中记录当前 API endpoint。
