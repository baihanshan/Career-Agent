JD_REQUIREMENTS_PROMPT = """
Extract structured job requirements from the job description.
Return only JSON matching the JDRequirement list schema.
Return a top-level JSON object with a "requirements" array.
Do not wrap the JSON in markdown fences.
Do not include explanations before or after the JSON.
Do not fabricate requirements that are not present in the job description.
Each item in "requirements" should include requirement_id, category, text, importance, and keywords.
Use requirement_id only as an internal stable identifier; never put internal IDs in text.
The text field must be user-readable JD wording or a concise user-readable summary of the original JD requirement.
High importance means explicit must-have, required, mandatory, core responsibility, or repeated/high-impact requirement.
Medium importance means relevant responsibility or skill that supports success but is not clearly mandatory.
Low importance means optional, preferred, bonus, nice-to-have, or weakly emphasized requirement.
""".strip()


APPLICATION_GENERATION_PROMPT = """
Generate evidence-only, evidence-grounded application assets from requirements, evidence, and match analysis.
Every user-experience claim must cite evidence_ids.
Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.
Missing requirements must not produce confident low-risk experience claims.
Return exactly 3 resume_bullets, ordered by JD match priority.
Use project and internship evidence first.
Use skills only as supporting context; never generate a standalone bullet from a skill list.
Internship bullets must include company name, project/work content, outcome, and tech stack when present in evidence.
Project bullets must include project name, personal contribution, tech stack, and result or measurable impact when present in evidence.
Do not generate a cover letter.
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
