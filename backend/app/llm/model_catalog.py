from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urljoin

import httpx

from backend.app.api.schemas import ModelListRequest, ModelListResponse, ModelOption


MODEL_LIST_TIMEOUT_SECONDS = 30


class ModelCatalogService:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.http_client = http_client or httpx.Client(timeout=MODEL_LIST_TIMEOUT_SECONDS)

    def list_models(self, request: ModelListRequest) -> ModelListResponse:
        if request.provider == "local":
            return ModelListResponse(models=[ModelOption(id="default")])
        if not request.api_key:
            raise ValueError("API key is required to list remote models.")

        url = _models_url(request)
        response = self.http_client.get(
            url,
            headers={"Authorization": f"Bearer {request.api_key}"},
        )
        response.raise_for_status()
        payload = response.json()
        models = _parse_models(payload)
        return ModelListResponse(models=models)


def _models_url(request: ModelListRequest) -> str:
    if request.provider == "openai":
        return "https://api.openai.com/v1/models"
    if request.provider == "deepseek":
        return "https://api.deepseek.com/models"
    if not request.base_url:
        raise ValueError("Base URL is required for compatible providers.")
    base_url = request.base_url.rstrip("/") + "/"
    return urljoin(base_url, "models")


def _parse_models(payload: Any) -> list[ModelOption]:
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    models: list[ModelOption] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, Mapping):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        normalized_id = model_id.strip()
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        owned_by = item.get("owned_by")
        models.append(
            ModelOption(
                id=normalized_id,
                owned_by=owned_by.strip() if isinstance(owned_by, str) else None,
            )
        )
    return sorted(models, key=lambda model: model.id)
