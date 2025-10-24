import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.app.config import get_settings
from backend.app.models import ContextBuildRequest
from backend.app.services import (
    ContextBuildServiceError,
    _normalise_query,
    _prepare_lists,
    build_context,
)


class DummyResponses:
    def __init__(self, payload):
        self.payload = payload
        self.captured = None

    async def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(output_text=json.dumps(self.payload))


class DummyClient:
    def __init__(self, payload):
        self.responses = DummyResponses(payload)


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("CROSSLENS_OPENAI_API_KEY", "test-key")
    yield
    get_settings.cache_clear()


def test_normalise_query_trims_and_deduplicates():
    assert _normalise_query("  Putin   e  Trump  ") == "Putin e Trump"


def test_normalise_query_raises_on_empty():
    with pytest.raises(ValueError):
        _normalise_query("   ")


def test_build_context_parses_payload():
    payload = {
        "nations_involved": ["rus", "USA"],
        "actors": [" Vladimir Putin ", ""],
        "organizations": ["Kremlin"],
        "topic_category": "geopolitica",
        "event_signature": "Summit Putin-Trump su Ucraina",
    }
    dummy_client = DummyClient(payload)

    request = ContextBuildRequest(query="  Putin   e Trump su Ucraina ")
    result = asyncio.run(build_context(request, client=dummy_client))  # type: ignore[arg-type]

    assert result.normalized_query == "Putin e Trump su Ucraina"
    assert result.nations_involved == ["RUS", "USA"]
    assert result.actors == ["Vladimir Putin"]
    assert result.organizations == ["Kremlin"]
    assert result.event_signature == "Summit Putin-Trump su Ucraina"

    captured = dummy_client.responses.captured
    assert captured["model"] == "o4-mini"
    assert captured["input"][1]["content"] == "Putin e Trump su Ucraina"


def test_build_context_requires_topic():
    payload = {
        "nations_involved": [],
        "actors": [],
        "organizations": [],
        "topic_category": "",
        "event_signature": "",
    }
    dummy_client = DummyClient(payload)
    request = ContextBuildRequest(query="Event")

    with pytest.raises(ContextBuildServiceError):
        asyncio.run(build_context(request, client=dummy_client))  # type: ignore[arg-type]


def test_build_context_requires_api_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("CROSSLENS_OPENAI_API_KEY", raising=False)
    payload = {
        "nations_involved": [],
        "actors": [],
        "organizations": [],
        "topic_category": "geopolitica",
        "event_signature": "evento",
    }
    dummy_client = DummyClient(payload)

    with pytest.raises(ContextBuildServiceError):
        asyncio.run(
            build_context(ContextBuildRequest(query="Evento"), client=dummy_client)  # type: ignore[arg-type]
        )


def test_prepare_lists_uppercase_and_trim():
    assert _prepare_lists([" itA ", ""], uppercase=True) == ["ITA"]
    assert _prepare_lists([" alpha ", "beta"], uppercase=False) == ["alpha", "beta"]
