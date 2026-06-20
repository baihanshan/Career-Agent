JD_REQUIREMENTS_PROMPT = """
Extract structured job requirements from the job description.
Return only JSON matching the JDRequirement list schema.
Return a top-level JSON object with a "requirements" array.
Do not wrap the JSON in markdown fences.
Do not include explanations before or after the JSON.
Do not fabricate requirements that are not present in the job description.
Each item in "requirements" must include requirement_id, category, text, importance,
keywords, capability_tags, verification_mode, interviewability, question_focus,
logical_operator, and alternatives.
Classify verification_mode as exactly one of:
- document_check: static qualifications visible in documents, such as degree or graduation date.
- evidence_check: capability that should be verified from resume project/internship evidence.
- technical_question: technical knowledge and engineering practice.
- system_design: scenario, platform, architecture, constraints, evaluation, or trade-offs.
- behavioral_question: collaboration, leadership, decisions, conflict, or retrospectives.
Set interviewability=false for document_check requirements. Never turn a degree requirement
into a question asking how the candidate satisfies the degree requirement.
Every interviewable requirement must have a concise, professional question_focus that names
the competency, scenario, constraints, or trade-offs to assess. Do not merely restate the JD.
Use normalized capability_tags such as programming, algorithms, machine_learning, nlp,
multimodal, platform, evaluation, system_design, communication, or leadership.
For requirements containing OR, "at least one", "任一", or "至少一个" logic, set
logical_operator="OR" and preserve each independent branch in alternatives. Do not flatten
OR branches into a list of capabilities that are all required. Otherwise use "AND".
Use requirement_id only as an internal stable identifier; never put internal IDs in text.
The text field must be user-readable JD wording or a concise user-readable summary of the original JD requirement.
High importance means explicit must-have, required, mandatory, core responsibility, or repeated/high-impact requirement.
Medium importance means relevant responsibility or skill that supports success but is not clearly mandatory.
Low importance means optional, preferred, bonus, nice-to-have, or weakly emphasized requirement.
""".strip()


APPLICATION_GENERATION_PROMPT = """
Generate evidence-only, evidence-grounded application assets from requirements, evidence, and match analysis.
Every user-experience claim must cite evidence_ids.
Evidence IDs and requirement IDs are internal JSON metadata only. Put them only in the
target_requirement_ids, evidence_ids, or supporting_evidence_ids fields. Never append,
quote, explain, or display IDs inside match_summary, resume bullet text, questions, or answers.
Never emit annotations such as `(evidence_ids: [...])`, `evidence_ids: []`, `req_*`,
`ev_*`, or `chunk_*` in user-visible text.
Use only evidence IDs present in the supplied EvidenceSelection and allowed-evidence context.
Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.
Missing requirements must not produce confident low-risk experience claims.
Return exactly 3 resume_bullets, ordered by JD match priority.
Use project and internship evidence first.
Use skills only as supporting context; never generate a standalone bullet from a skill list.
Contextual skill-only support must not be rewritten as a project, internship, production
achievement, employer claim, metric, or practical outcome.
Internship bullets must include company name, project/work content, outcome, and tech stack when present in evidence.
Project bullets must include project name, personal contribution, tech stack, and result or measurable impact when present in evidence.
Do not generate a cover letter.
Set interview_prep to an object with empty jd_questions and resume_deep_dive_questions arrays;
the Interview Prep Agent generates those answers in the next workflow step.
Return only JSON matching the GeneratedAssets schema.
Do not wrap the JSON in markdown fences.
Do not include explanations before or after the JSON.
""".strip()


GROUNDING_EVALUATION_PROMPT = """
Evaluate whether generated claims are supported by the provided evidence snippets.
Do not fabricate evidence or silently excuse unsupported claims.
Return only JSON matching the EvaluationReport schema.
Do not wrap the JSON in markdown fences.
Do not include explanations before or after the JSON.
""".strip()
