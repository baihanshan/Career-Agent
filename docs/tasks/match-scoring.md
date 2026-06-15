# Match Scoring 模块任务

## 目标

实现可解释的岗位匹配评分，把 JD requirements 和 evidence items 转化为 `MatchItem[]`。

## 依赖

- `data-models.md`
- `retrieval.md`

## 完成标准

- 每个 requirement 都有一个 MatchItem。
- 无 evidence 时必须是 `missing`。
- 低分 evidence 不会被标记为 `strong`。
- MatchItem 中的 evidence id 必须能追溯到 evidence table。

## 最小任务清单

- [ ] 创建 `backend/app/workflow/match_scoring.py`。
- [ ] 创建 `backend/tests/test_match_scoring.py`。
- [ ] 写测试：无 evidence 的 requirement 返回 `missing`。
- [ ] 实现 `score_requirement(requirement, evidence_items)` 的 missing 分支。
- [ ] 运行 missing 测试。
- [ ] 写测试：高分 evidence 返回 `strong` 或 `partial`。
- [ ] 实现高分 evidence 评分规则。
- [ ] 写测试：低分 evidence 返回 `weak`。
- [ ] 实现 weak 评分规则。
- [ ] 写测试：每个 requirement 都生成一个 MatchItem。
- [ ] 实现 `score_matches(requirements, evidence_items)`。
- [ ] 写测试：MatchItem 的 evidence ids 全部存在于 evidence table。
- [ ] 实现 evidence id 校验或过滤。
- [ ] 运行 match scoring 测试。
