from __future__ import annotations

from pathlib import Path

from backend.app.api.schemas import EvaluationReport, GeneratedAssets, JDRequirement
from backend.app.llm.client import FakeLLMClient


FIXTURE_DIR = Path(__file__).parent


def load_sample_profile() -> str:
    return _read_text("sample_profile.md")


def load_sample_jd() -> str:
    return _read_text("sample_jd.txt")


def load_fake_llm_jd_requirements() -> list[JDRequirement]:
    return [JDRequirement.model_validate(item) for item in _read_json("fake_llm_jd_requirements.json")]


def load_fake_llm_generated_assets() -> GeneratedAssets:
    return GeneratedAssets.model_validate(_read_json("fake_llm_generated_assets.json"))


def load_fake_llm_evaluation() -> EvaluationReport:
    return EvaluationReport.model_validate(_read_json("fake_llm_evaluation.json"))


def load_fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient(
        responses={
            "extract_jd_requirements": _read_text("fake_llm_jd_requirements.json"),
            "generate_application_assets": _read_text("fake_llm_generated_assets.json"),
            "evaluate_claim_grounding": _read_text("fake_llm_evaluation.json"),
        }
    )


def _read_text(filename: str) -> str:
    return (FIXTURE_DIR / filename).read_text(encoding="utf-8")


def _read_json(filename: str):
    import json

    return json.loads(_read_text(filename))
