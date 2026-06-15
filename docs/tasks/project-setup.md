# Project Setup 模块任务

## 目标

建立 CareerPilot Agent 的最小工程骨架，使后端、前端、测试和文档可以按模块独立推进。

## 依赖

无。建议第一个执行。

## 完成标准

- 后端与前端目录存在。
- 有最小可运行的开发命令。
- 有测试命令入口。
- README 中说明本地启动方式。

## 最小任务清单

- [x] 创建 `backend/` 目录。
- [x] 创建 `backend/app/` 目录。
- [x] 创建 `backend/app/__init__.py`。
- [x] 创建 `backend/tests/` 目录。
- [x] 创建 `frontend/` 目录。
- [x] 创建 `docs/tasks/` 目录并保留当前任务文件。
- [x] 选择后端包管理方式，并记录在 README 中。
- [x] 创建后端测试配置，使 `pytest` 能发现 `backend/tests/`。
- [x] 创建后端 app 入口占位文件 `backend/app/main.py`。
- [x] 创建前端 app 入口占位结构。
- [x] 添加 `.env.example`，列出 `OPENAI_API_KEY`、`CHROMA_PATH`、`APP_ENV`。
- [x] 添加 `.gitignore`，忽略 `.env`、Python cache、Node modules、Chroma 本地数据。
- [x] 在 README 中写明 MVP 范围。
- [x] 在 README 中写明非 MVP 范围：自动投递、浏览器控制、多用户登录、支付、社交功能、复杂简历排版。
- [x] 运行后端测试命令，确认空测试环境不报配置错误。
- [x] 运行前端基础命令，确认项目骨架可启动或可构建。
