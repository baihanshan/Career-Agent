# DeepSeek ReAct 工具调用兼容性修复设计

## 背景与已确认事实

网页分析请求返回 HTTP 200，但业务状态为 `failed`，错误码为
`REACT_TOOL_CALL_ERROR`，失败发生在 `ResumeEvidenceAgent`。仓库标准测试简历和
JD 同样能够复现，因此问题与 PDF 提取文本无关。

使用同一套 BGE、Chroma、文档切分和质量门禁，仅将模型切换为本地确定性
ReAct 模型后，分析能够完成。这将故障范围限定在 DeepSeek ChatModel 与
LangGraph 结构化工具调用的兼容边界。

## 目标

1. 保留三个模块的真实 LLM ReAct 架构，不增加确定性业务降级。
2. 让 DeepSeek 生成的合法工具调用能够稳定执行并通过既有质量门禁。
3. 工具参数或工具执行真实失败时，返回准确且脱敏的错误类别，不再误报为
   “简历没有可用证据”。
4. 保留 Pydantic 参数校验、证据 ID 白名单、数字校验和最终质量门禁。

## 非目标

- 不将证据选择改回纯规则实现。
- 不在 ReAct 失败后自动伪造或确定性生成最终选择。
- 不放宽 evidence ID 白名单或质量门禁。
- 不修改 PDF 解析流程。

## 方案

### 1. Provider 工具调用配置

由 `ReActModelFactory` 统一携带 provider 能力信息。DeepSeek 模型在绑定工具时
关闭并行工具调用，使共享的检索状态、Chroma 查询和 evidence allowlist 按顺序
更新；OpenAI 及测试模型保持现有行为。Agent 工厂接收已配置的模型，不在各
Agent 内复制 provider 判断。

### 2. 严格而可恢复的参数处理

工具参数继续由 Pydantic schema 校验。可选字段使用 schema 默认值；
`requirement_id` 必须来自当前 JD 白名单。模型给出未知 ID 时返回结构化、可重试
的工具错误，并向下一次 ReAct 调用提供允许的 requirement ID 摘要，不跨要求
搜索，也不静默修正为其他 ID。

### 3. 错误分类与可观测性

结构化工具包装器区分：参数校验失败、未知内部引用、检索执行异常和工具返回的
受控错误。日志只记录异常类型、工具名、attempt、状态和脱敏摘要；不记录简历
正文、API Key、完整 prompt 或隐藏推理。

最终错误保持公开安全：

- 工具参数/调用失败：`REACT_TOOL_CALL_ERROR`
- Agent 最终 JSON 无法解析：`REACT_OUTPUT_PARSE_ERROR`
- 证据 ID 越界：`REACT_EVIDENCE_VIOLATION`
- 质量门禁失败：`REACT_QUALITY_GATE_FAILED`

`nodes.py` 不再把上述错误统一改写成“没有可用简历证据”。前端为每个 ReAct
错误码提供对应中文提示，但不展示内部 ID、trace 或供应商原始响应。

## 数据流

1. `ReActModelFactory` 根据 provider 创建并配置 ChatModel。
2. Resume Evidence Agent 请求模型生成结构化工具调用。
3. 工具 schema 校验参数并验证 requirement ID 白名单。
4. 工具串行执行检索，更新候选证据和 allowlist。
5. Agent 返回 `EvidenceSelection`，既有质量门禁完成最终校验。
6. 成功则继续后续 Agent；失败则按真实错误类别结束并返回安全提示。

## 测试设计

- 模型工厂：DeepSeek 绑定工具时禁用并行调用；其他 provider 不受影响。
- 工具层：默认可选参数、未知 requirement ID、检索异常均产生稳定结构化结果。
- Agent 层：一次错误工具调用后能够读取反馈并用合法参数重试；最终错误不会被
  早期错误错误归类。
- Workflow：Resume Evidence 工具失败返回准确公开错误，不误报证据缺失。
- Frontend：所有 ReAct 错误码均映射为受控中文提示，且不渲染后端 details。
- 回归：完整后端测试、前端 check/build，以及本地确定性端到端分析。

## 成功标准

- DeepSeek 合法工具调用不再因并行共享状态或参数兼容问题失败。
- 标准 fixture 能进入 Resume Evidence Agent 后续节点；若供应商仍返回非法调用，
  页面显示准确的工具调用错误而不是“请检查输入”或“没有项目经历”。
- 现有证据、数字和公开输出安全测试全部通过。
