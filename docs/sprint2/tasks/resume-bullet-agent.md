# Sprint 2 Resume Bullet Agent 任务

状态：已完成

## 目标

生成 3 条高质量简历要点，优先使用项目和实习经历，不从技能列表单独生成。

## 依赖

- `docs/sprint2/improve.md`
- `docs/sprint2/match-strategist-agent.md`
- `backend/app/workflow/writer.py`

## 完成标准

- 固定生成 3 条简历要点。
- 按 JD 匹配度排序。
- 实习要点包含公司名、项目内容、成果和技术栈。
- 项目要点包含项目名称、项目目标、个人贡献、技术栈、结果或可量化影响。
- 内部保留 evidence 引用。
- 不再生成 cover letter。

## 最小任务清单

- [x] 删除 writer 中 cover letter 面向前端输出逻辑。
- [x] 更新生成 prompt，明确技能列表只能作为辅助。
- [x] 更新生成 prompt，要求项目/实习经历优先。
- [x] 更新输出 schema，确保 resume_bullets 固定 3 条。
- [x] 每条 bullet 保留内部 evidence_ids。
- [x] 每条 bullet 面向前端展示时不展示内部 requirement ID。
- [x] 编写测试：技能列表不会单独生成 bullet。
- [x] 编写测试：实习 bullet 包含公司名、项目内容、成果和技术栈。
- [x] 编写测试：项目 bullet 包含项目名、贡献、技术栈和结果。
- [x] 编写测试：输出正好 3 条 bullet。
