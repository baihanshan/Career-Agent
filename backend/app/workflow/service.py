from __future__ import annotations

from uuid import uuid4

from backend.app.api.schemas import AnalysisRequest


def run_analysis(request: AnalysisRequest) -> dict:
    """Temporary workflow facade until the LangGraph module is implemented."""
    return {
        "analysis_id": f"analysis_{uuid4().hex}",
        "status": "completed",
        "result": {
            "jd_requirements": [],
            "evidence_table": [],
            "match_analysis": [],
            "generated_assets": {},
            "evaluation_report": {},
            "profile_document_count": len(request.profile_documents),
        },
    }
