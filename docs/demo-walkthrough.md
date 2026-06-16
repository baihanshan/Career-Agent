# CareerPilot Agent Demo Walkthrough

This walkthrough uses stable fixtures so the demo can run without a live LLM provider.

## 1. Start The Backend

From the project root:

```bash
conda activate carrer_agent
conda run -n carrer_agent uvicorn backend.app.main:app --reload
```

The backend should be available at `http://localhost:8000`.

You can confirm it is running with:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 2. Start The Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## 3. Enter Sample Profile

Open `backend/tests/fixtures/sample_profile.md` and paste the full file into the `个人材料` field.

The sample profile includes:

- Education background
- AI course project
- Technical skills
- GitHub portfolio project

## 4. Enter Sample JD

Open `backend/tests/fixtures/sample_jd.txt` and paste the full file into the `目标岗位 JD` field.

The sample JD includes:

- Python API hard skills
- Retrieval and evidence-grounded generation responsibilities
- Collaboration requirements
- LangGraph workflow nice-to-have experience

## 5. Run Analysis

Click `开始分析`.

The frontend should show:

- `匹配总结`
- `简历要点`
- `求职信草稿`
- `面试准备`
- `证据表`
- `流程警告` when applicable
- `风险提示`

## 6. Inspect Evidence References

In `简历要点`, each grounded bullet shows evidence chips such as:

```text
证据来源：req_python_api:evidence:1
```

In `证据表`, inspect:

- `source_name`
- `section_label`
- evidence snippet
- retrieval score
- evidence id

This is the core evidence-grounding behavior: generated claims should be traceable back to profile material.

## 7. Inspect Grounding Warnings

The `风险提示` panel displays evaluator output:

- grounding warnings
- coverage gaps
- specificity notes
- overall risk summary

If a generated claim includes unsupported numbers or lacks evidence ids, evaluator warnings should make that visible instead of silently accepting the claim.

## 8. Run Test Fixture Workflow

The same sample data can be verified from tests:

```bash
conda run -n carrer_agent python -m pytest backend/tests/test_testing_fixtures.py backend/tests/test_workflow_integration.py
```

These tests prove the fixture profile, fixture JD, fake LLM outputs, retrieval, writer, evaluator, and workflow can run as a stable end-to-end path.
