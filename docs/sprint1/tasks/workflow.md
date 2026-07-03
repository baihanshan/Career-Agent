# Workflow 模块任务

## 目标

用 LangGraph 编排 parse inputs、index profile、analyze JD、retrieve evidence、score match、write application、evaluate grounding、finalize response。

## 依赖

- `data-models.md`
- `document-processing.md`
- `retrieval.md`
- `llm-service.md`
- `match-scoring.md`
- `writer.md`
- `evaluator.md`

## 完成标准

- workflow state 包含 detailed-design 中定义的核心字段。
- 每个节点可以独立测试。
- 完整 workflow 可以用 fixture 输入跑到 final response。
- vector store failure 和 LLM parser error 有明确中断或重试行为。

## 最小任务清单

- [x] 创建 `backend/app/workflow/nodes.py`。
- [x] 创建 `backend/app/workflow/graph.py`。
- [x] 创建 `backend/tests/test_workflow_nodes.py`。
- [x] 创建 `backend/tests/test_workflow_integration.py`。
- [x] 实现 `AnalysisState`。
- [x] 写测试：`parse_inputs` 为合法 request 生成 analysis id。
- [x] 实现 `parse_inputs` 节点。
- [x] 写测试：`index_profile` 调用 document processing 和 retrieval。
- [x] 实现 `index_profile` 节点。
- [x] 写测试：`analyze_jd` 调用 LLM service 并写入 requirements。
- [x] 实现 `analyze_jd` 节点。
- [x] 写测试：`retrieve_evidence` 写入 evidence table。
- [x] 实现 `retrieve_evidence` 节点。
- [x] 写测试：`score_match` 写入 match analysis。
- [x] 实现 `score_match` 节点。
- [x] 写测试：`write_application` 写入 generated assets。
- [x] 实现 `write_application` 节点。
- [x] 写测试：`evaluate_grounding` 写入 evaluation report。
- [x] 实现 `evaluate_grounding` 节点。
- [x] 写测试：`finalize_response` 输出 API response result。
- [x] 实现 `finalize_response` 节点。
- [x] 定义 LangGraph 节点顺序。
- [x] 写集成测试：sample profile 和 sample JD 可以跑完整 workflow。
- [x] 写测试：LLM parser error 重试一次。
- [x] 写测试：vector store failure 中断并返回 indexing error。
- [x] 运行 workflow 测试。
