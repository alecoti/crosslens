import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.app.config import get_settings
from backend.app.models import (
    FramesAnalyzeRequest,
    ResolvedSource,
    SearchCountryResults,
    SearchResultItem,
)
from backend.app.services import (
    ArticleExtraction,
    ArticleExtractionError,
    FrameAnalysisServiceError,
    analyze_frames,
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


class SuccessfulExtractor:
    async def extract(self, url: str):
        return ArticleExtraction(text="Full article body", partial=False)


class FailingExtractor:
    async def extract(self, url: str):
        raise ArticleExtractionError("boom")


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("CROSSLENS_OPENAI_API_KEY", "test-key")
    yield
    get_settings.cache_clear()


def _build_request() -> FramesAnalyzeRequest:
    return FramesAnalyzeRequest(
        event_signature="Summit Putin-Trump su Ucraina",
        per_country_results=[
            SearchCountryResults(
                country="USA",
                items=[
                    SearchResultItem(
                        source="NYTimes",
                        domain="nytimes.com",
                        url="https://www.nytimes.com/article",
                        title="Titolo articolo",
                        snippet="Riassunto della notizia",
                    )
                ],
            )
        ],
        resolved_sources=[
            ResolvedSource(country="USA", source="NYTimes", orientation="center-left ANTITRUMP")
        ],
    )


def test_analyze_frames_returns_frame_card():
    payload = {
        "tone": "analitico",
        "stance": "critico",
        "frame_label": "Focus su compromesso",
        "key_claims": ["Claim 1", "Claim 2"],
        "evidence_level": "alto",
        "orientation_detected": "critico",
        "partial": False,
    }
    dummy_client = DummyClient(payload)

    response = asyncio.run(
        analyze_frames(
            _build_request(),
            client=dummy_client,
            extractor=SuccessfulExtractor(),
        )
    )

    assert response.event_signature == "Summit Putin-Trump su Ucraina"
    assert len(response.frames) == 1
    frame = response.frames[0]
    assert frame.country == "USA"
    assert frame.frame_card.orientation_inherited == "center-left ANTITRUMP"
    assert frame.frame_card.orientation_detected == "critico"
    assert frame.frame_card.partial is False
    assert frame.extracted_text == "Full article body"

    captured_prompt = dummy_client.responses.captured["input"][1]["content"]
    assert "Orientation inherited: center-left ANTITRUMP" in captured_prompt
    assert "Full article body" in captured_prompt


def test_analyze_frames_marks_partial_on_extraction_failure():
    payload = {
        "tone": "emotivo",
        "stance": "favorevole",
        "frame_label": "Putin pacificatore",
        "key_claims": ["Claim"],
        "evidence_level": "medio",
        "partial": False,
    }
    dummy_client = DummyClient(payload)

    response = asyncio.run(
        analyze_frames(
            _build_request(),
            client=dummy_client,
            extractor=FailingExtractor(),
        )
    )

    frame = response.frames[0]
    assert frame.extracted_text is None
    assert frame.frame_card.partial is True
    assert frame.frame_card.key_claims == ["Claim"]


def test_analyze_frames_errors_when_key_claims_missing():
    payload = {
        "tone": "analitico",
        "stance": "critico",
        "frame_label": "Cornice",
        "key_claims": [],
        "evidence_level": "alto",
        "partial": False,
    }
    dummy_client = DummyClient(payload)

    with pytest.raises(FrameAnalysisServiceError):
        asyncio.run(
            analyze_frames(
                _build_request(),
                client=dummy_client,
                extractor=SuccessfulExtractor(),
            )
        )
