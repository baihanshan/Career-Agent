JD_REQUIREMENTS_PROMPT = """
Extract structured job requirements from the job description.
Return only JSON matching the JDRequirement list schema.
Return a top-level JSON object with a "requirements" array.
Do not wrap the JSON in markdown fences.
Do not include explanations before or after the JSON.
Do not fabricate requirements that are not present in the job description.
Each item in "requirements" should include requirement_id, category, text, importance, and keywords.
""".strip()


APPLICATION_GENERATION_PROMPT = """
Generate evidence-only, evidence-grounded application assets from requirements, evidence, and match analysis.
Every user-experience claim must cite evidence_ids.
Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.
Missing requirements must not produce confident low-risk experience claims.
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
