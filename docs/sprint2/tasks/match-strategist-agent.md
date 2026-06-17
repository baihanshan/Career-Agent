# Sprint 2 Match Strategist Agent 任务

## 目标

根据 JD requirements 和 evidence items 生成匹配策略，指导简历要点、面试准备和风险评估。

## 依赖

- `docs/sprint2/improve.md`
- `backend/app/workflow/match_scoring.py`

## 完成标准

- 输出 strong、partial、weak、missing。
- 能识别最值得写入简历要点的项目/实习证据。
- 按 JD 匹配度排序 evidence。
- 不使用 ReAct。

## 最小任务清单

- [ ] 扩展 match scoring 输入，包含 section_type。
- [ ] 对 project/internship evidence 增加优先级加权。
- [ ] 对 skill evidence 降低生成优先级。
- [ ] 生成 `match_strategy`，包含 top experiences、covered requirements、missing requirements。
- [ ] 支持 LLM rerank，但保留 deterministic scoring baseline。
- [ ] 编写测试：project evidence 分数相近时优先于 skill evidence。
- [ ] 编写测试：missing requirement 进入 match_strategy。
- [ ] 编写测试：top 3 简历要点候选按 JD 匹配度排序。

