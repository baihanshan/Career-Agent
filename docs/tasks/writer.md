# Writer 模块任务

## 目标

实现求职内容生成模块，输出岗位匹配总结、定制化简历 bullet、cover letter 草稿和面试准备建议。

## 依赖

- `data-models.md`
- `llm-service.md`
- `match-scoring.md`

## 完成标准

- 生成结果符合 `GeneratedAssets` schema。
- 每条 resume bullet 包含 `target_requirement_ids` 和 `evidence_ids`。
- 没有 evidence 的 requirement 不生成自信经历陈述。
- writer prompt 明确禁止编造雇主、日期、数字、工具和成果。

## 最小任务清单

- [ ] 创建 `backend/app/workflow/writer.py`。
- [ ] 创建 `backend/tests/test_writer.py`。
- [ ] 写测试：writer 输入 requirements、evidence、match items 后返回 `GeneratedAssets`。
- [ ] 实现 `build_writer_context(...)`。
- [ ] 实现 `write_application(...)`，先接入 fake LLM。
- [ ] 写测试：每条 resume bullet 至少包含一个 evidence id，或 risk_level 为 high。
- [ ] 实现 bullet evidence 校验。
- [ ] 写测试：missing requirement 不生成 low-risk bullet。
- [ ] 实现 missing requirement 的降级处理。
- [ ] 写测试：cover letter 包含 opening、body、closing。
- [ ] 确保 cover letter parser 生成完整结构。
- [ ] 写测试：interview prep item 包含 topic、why_it_matters、prep_suggestion。
- [ ] 确保 interview prep parser 生成完整结构。
- [ ] 在 writer prompt 中加入 evidence-only 约束。
- [ ] 运行 writer 测试。
