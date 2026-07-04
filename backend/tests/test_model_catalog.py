import httpx
import pytest

from backend.app.api.schemas import ModelListRequest
from backend.app.llm.model_catalog import ModelCatalogService


def test_model_catalog_lists_deepseek_models():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "deepseek-reasoner", "owned_by": "deepseek"},
                    {"id": "deepseek-chat", "owned_by": "deepseek"},
                    {"id": "deepseek-chat", "owned_by": "deepseek"},
                ]
            },
        )

    service = ModelCatalogService(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    response = service.list_models(
        ModelListRequest(
            provider="deepseek",
            api_key="secret-key",
            base_url="https://api.deepseek.com",
        )
    )

    assert [model.id for model in response.models] == [
        "deepseek-chat",
        "deepseek-reasoner",
    ]
    assert requests[0].url == "https://api.deepseek.com/models"
    assert requests[0].headers["authorization"] == "Bearer secret-key"


def test_model_catalog_uses_compatible_base_url():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "custom-model"}]})

    service = ModelCatalogService(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    response = service.list_models(
        ModelListRequest(
            provider="openai_compatible",
            api_key="secret-key",
            base_url="https://example.com/v1",
        )
    )

    assert [model.id for model in response.models] == ["custom-model"]
    assert requests[0].url == "https://example.com/v1/models"


def test_model_catalog_requires_api_key_for_remote_provider():
    service = ModelCatalogService(
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: pytest.fail("no request"))
        )
    )

    with pytest.raises(ValueError):
        service.list_models(ModelListRequest(provider="openai"))
