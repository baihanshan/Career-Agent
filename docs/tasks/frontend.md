# Frontend 模块任务

## 目标

实现 MVP 单页前端：输入个人材料和 JD，触发分析，展示运行状态、结果、证据引用和风险提示。

## 依赖

- `backend-api.md`
- `data-models.md`

## 完成标准

- 用户可以粘贴 profile materials 和 job description。
- 用户可以提交 analysis。
- loading、success、error 状态清晰。
- 结果区展示 match summary、evidence table、resume bullets、cover letter、interview prep。
- warning 和 evidence source 可见。

## 最小任务清单

- [ ] 创建 `frontend/lib/api.ts`。
- [ ] 创建 `frontend/lib/types.ts` 或复用 data models 任务中的类型文件。
- [ ] 创建 `frontend/app/page.tsx`。
- [ ] 创建 `frontend/components/ProfileInput.tsx`。
- [ ] 创建 `frontend/components/JobDescriptionInput.tsx`。
- [ ] 创建 `frontend/components/RunStatus.tsx`。
- [ ] 创建 `frontend/components/ResultView.tsx`。
- [ ] 创建 `frontend/components/EvidenceTable.tsx`。
- [ ] 创建 `frontend/components/RiskWarnings.tsx`。
- [ ] 写测试：空输入时提交按钮不可用或显示错误。
- [ ] 实现 profile materials 输入框。
- [ ] 实现 JD 输入框。
- [ ] 实现 submit handler，调用 `/analysis`。
- [ ] 写测试：提交后显示 loading 状态。
- [ ] 实现 loading 状态。
- [ ] 写测试：completed response 渲染 match summary。
- [ ] 实现 match summary 渲染。
- [ ] 写测试：evidence table 显示 source name 和 snippet。
- [ ] 实现 evidence table。
- [ ] 写测试：resume bullets 显示 evidence ids 或 source references。
- [ ] 实现 resume bullets 区块。
- [ ] 写测试：cover letter 区块显示 opening、body、closing。
- [ ] 实现 cover letter 区块。
- [ ] 写测试：interview prep 区块显示 topic 和 prep suggestion。
- [ ] 实现 interview prep 区块。
- [ ] 写测试：grounding warnings 显示 severity。
- [ ] 实现 risk warnings 区块。
- [ ] 运行前端测试。
