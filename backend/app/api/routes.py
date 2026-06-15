from fastapi import APIRouter

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.workflow import service


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analysis", response_model=AnalysisResponse)
def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    return AnalysisResponse.model_validate(service.run_analysis(request))
