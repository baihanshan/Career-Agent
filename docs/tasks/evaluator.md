# Evaluator 模块任务

## 目标

实现评估模块，检查生成内容的 grounding、coverage、specificity 和 hallucination risk。

## 依赖

- `data-models.md`
- `writer.md`

## 完成标准

- 无 evidence id 的 bullet 会被标记。
- 编造数字、雇主、工具或成果会被标记。
- 未覆盖 high importance requirement 会产生 coverage gap。
- evaluator 输出 `EvaluationReport`。

## 最小任务清单

- [ ] 创建 `backend/app/evaluation/evaluator.py`。
- [ ] 创建 `backend/tests/test_evaluator.py`。
- [ ] 写测试：无 evidence id 的 resume bullet 产生 grounding warning。
- [ ] 实现 evidence id 存在性检查。
- [ ] 写测试：生成内容出现 evidence 中没有的数字会产生 high severity warning。
- [ ] 实现数字一致性检查。
- [ ] 写测试：high importance requirement 未被生成内容覆盖会产生 coverage gap。
- [ ] 实现 coverage 检查。
- [ ] 写测试：泛泛 bullet 产生 specificity note。
- [ ] 实现 specificity 检查。
- [ ] 写测试：有 warning 时 `overall_status` 为 `pass_with_warnings` 或 `fail`。
- [ ] 实现 overall status 汇总逻辑。
- [ ] 接入 LLM semantic grounding 判断接口，但保留 fake client 测试路径。
- [ ] 运行 evaluator 测试。
