JD_REQUIREMENTS_PROMPT = """
Extract structured job requirements from the job description.
Return only JSON matching the JDRequirement list schema.
Do not fabricate requirements that are not present in the job description.
""".strip()


APPLICATION_GENERATION_PROMPT = """
Generate evidence-grounded application assets from requirements, evidence, and match analysis.
Every user-experience claim must cite evidence_ids.
Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.
Return only JSON matching the GeneratedAssets schema.
""".strip()


GROUNDING_EVALUATION_PROMPT = """
Evaluate whether generated claims are supported by the provided evidence snippets.
Do not fabricate evidence or silently excuse unsupported claims.
Return only JSON matching the EvaluationReport schema.
""".strip()
