# Sprint 2 Frontend Output 任务

状态：已完成

## 目标

调整前端展示模块，删除求职信和证据表，突出匹配摘要、简历要点、面试准备、风险提示和可展开分析过程。

## 依赖

- `docs/sprint2/improve.md`
- `frontend/app/page.tsx`
- `frontend/components/ResultView.tsx`
- `frontend/lib/types.ts`

## 完成标准

- 前端不展示 cover letter。
- 前端不展示 evidence table。
- 展示顺序为匹配摘要、简历要点、面试准备、风险提示、分析过程详情。
- 面试准备分为 JD 相关问题和简历深挖问题。
- 风险提示最多 3 条，不显示内部 requirement ID。
- Agent trace 默认折叠，可展开。

## 最小任务清单

- [x] 更新 TypeScript types，移除前端展示用 cover letter。
- [x] 更新 ResultView，删除求职信模块。
- [x] 更新 ResultView，删除证据表模块。
- [x] 新增匹配摘要模块。
- [x] 更新简历要点模块，展示 3 条按 JD 匹配度排序的 bullet。
- [x] 新增面试准备分组展示：JD 相关问题、简历深挖问题。
- [x] 新增风险提示模块，最多展示 3 条。
- [x] 新增分析过程详情折叠模块。
- [x] 错误状态展示用户友好提示，不展示内部 Agent 异常。
- [x] 编写前端结构检查，确保中文 UI 文案存在。
- [x] 运行 `npm run check`。
- [x] 运行 `npm run build`。
