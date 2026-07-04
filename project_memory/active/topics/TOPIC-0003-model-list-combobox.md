---
id: TOPIC-0003
title: 模型名自动获取与可输入下拉框
status: active
level: P1
tags:
  - frontend
  - backend
  - llm
  - api-contract
use_when: 修改前端模型设置、`/models/list`、模型名下拉/手动输入、OpenAI/DeepSeek/openai-compatible 模型列表获取逻辑。
updated: 2026-07-04
---

# TOPIC-0003：模型名自动获取与可输入下拉框

## 设计约定

前端模型服务只保留 `OpenAI`、`DeepSeek`、`兼容接口` 和 `本地演示`。不要再添加大量具体第三方供应商 preset；第三方服务通过 `openai_compatible` 加 Base URL 接入。

模型名输入框是 combo-box 行为：用户可点击「获取模型列表」从后端代理获取 provider `/models` 返回的模型 ID，然后通过原生 `datalist` 下拉选择；也可以忽略下拉，直接手动输入任意模型名。

## API 契约

后端新增：

```text
POST /models/list
```

请求使用 `ModelListRequest`：

- `provider`: `local | openai | deepseek | openai_compatible`
- `api_key`: 远程 provider 必填，本地演示不需要
- `base_url`: `openai_compatible` 必填；DeepSeek 默认使用 `https://api.deepseek.com/models`；OpenAI 默认使用 `https://api.openai.com/v1/models`

响应使用 `ModelListResponse`：

- `models`: `[{ id, owned_by }]`
- `warning`: 获取失败时返回受控中文提示；失败不阻断手动输入

API key 只用于本次请求，不保存，不回显到响应。

## 前端行为

`LlmSettings` 中模型输入框保留普通文本输入能力，并在已有 `modelOptions` 时绑定 `datalist`。用户点击「获取模型列表」后：

- 成功：显示可选模型，并提示已获取数量；
- 无模型：提示手动输入；
- 失败：显示受控中文错误，仍允许手动输入。

本地演示禁用远程获取，继续使用默认 `default`。

## 验证

已执行：

```bash
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_model_catalog.py backend/tests/test_api.py
npm run check
npm run build
RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q
```

结果：全部通过。`npm run build` 仅有既有 Next SWC 本地包加载 warning；完整后端测试仅有既有 `StarletteDeprecationWarning`。
