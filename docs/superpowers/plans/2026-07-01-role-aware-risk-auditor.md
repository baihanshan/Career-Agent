# Role-Aware Risk Auditor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Risk Auditor prioritize real role-specific screening risks instead of mechanically surfacing generic JD soft-skill gaps.

**Architecture:** Keep the public API unchanged. Add internal role-aware audit policy to the Risk Auditor invocation payload and prompt, and make candidate risk ranking consider role/core-risk priority before generic soft skills. Cover the behavior with focused backend tests.

**Tech Stack:** FastAPI backend, LangChain ReAct agent, Pydantic models, pytest.

---

### Task 1: Add Failing Tests For Role-Aware Risk Priority

**Files:**
- Modify: `backend/tests/test_risk_auditor_agent.py`

- [ ] **Step 1: Write tests that fail against current behavior**

Add tests asserting that the prompt/payload includes role-aware policy, and that risk ranking puts a high-priority technical gap ahead of a generic communication gap even when both have the same severity.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_risk_auditor_agent.py`

Expected: FAIL because current prompt has no role-type policy and ranking only sorts by severity.

### Task 2: Add Role-Aware Policy To Risk Auditor Prompt And Invocation

**Files:**
- Modify: `backend/app/workflow/risk_auditor_agent.py`

- [ ] **Step 1: Update `RISK_AUDITOR_AGENT_PROMPT`**

Add instructions requiring the agent to classify the role first, prioritize core screening dimensions by role type, and down-rank generic soft skills unless they are truly role-critical and not indirectly proven by project or team evidence.

- [ ] **Step 2: Add `risk_audit_policy` to `_invocation_prompt`**

Include internal policy fields for role type options, technical-role priority order, product/project-role priority order, and soft-skill downranking rules.

### Task 3: Rank Candidate Risks By Core-Screening Priority

**Files:**
- Modify: `backend/app/workflow/react_tools.py`
- Modify: `backend/app/workflow/risk_auditor_agent.py`

- [ ] **Step 1: Update `rank_candidate_risks`**

Sort candidate risks by severity, then by explicit `risk_priority`, then by role-core `risk_dimension`, so technical/project-depth/engineering gaps outrank soft-skill gaps.

- [ ] **Step 2: Update deterministic final normalization**

When final reports contain optional priority metadata in risk dicts, preserve public schema compatibility and keep deterministic top-three ordering by severity and requirement importance.

### Task 4: Verify

**Files:**
- Test: `backend/tests/test_risk_auditor_agent.py`

- [ ] **Step 1: Run focused tests**

Run: `RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q backend/tests/test_risk_auditor_agent.py`

- [ ] **Step 2: Run broader backend tests**

Run: `RETRIEVAL_BACKEND=fake conda run -n carrer_agent pytest -q`

- [ ] **Step 3: Update project memory**

Update `project_memory/handoff.md` with the new Risk Auditor behavior and verification evidence, then run `python3 /Users/baihanshan/.codex/skills/project-memory/scripts/redact_secrets.py --path project_memory`.

