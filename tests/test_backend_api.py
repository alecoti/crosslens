import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models import (
    ArticleFrame,
    ContextBuildRequest,
    ContextBuildResponse,
    FrameCard,
    FramesAnalyzeRequest,
    FramesAnalyzeResponse,
)
from backend.app.services import FrameAnalysisServiceError


@pytest.fixture
def client():
    return TestClient(app)


def test_healthcheck(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_context_build_endpoint(monkeypatch, client):
    fake_response = ContextBuildResponse(
        normalized_query="Putin e Trump si incontrano",
        nations_involved=["RUS", "USA"],
        actors=["Vladimir Putin", "Donald Trump"],
        organizations=["Kremlin"],
        topic_category="geopolitica",
        event_signature="Summit Putin-Trump su Ucraina",
    )

    async def _fake_service(request: ContextBuildRequest):
        assert request.query == "Putin  e   Trump si incontrano"
        return fake_response

    monkeypatch.setattr("backend.app.main.build_context", _fake_service)

    response = client.post(
        "/v1/context/build",
        json={"query": "Putin  e   Trump si incontrano"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_signature"] == fake_response.event_signature


def test_context_build_rejects_blank(client):
    response = client.post(
        "/v1/context/build",
        json={"query": "   "},
    )
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


def test_frames_analyze_endpoint(monkeypatch, client):
    fake_response = FramesAnalyzeResponse(
        event_signature="Summit",
        frames=[
            ArticleFrame(
                country="USA",
                source="NYTimes",
                domain="nytimes.com",
                url="https://www.nytimes.com/1",
                title="Titolo",
                snippet="Snippet",
                extracted_text="Body",
                frame_card=FrameCard(
                    tone="analitico",
                    stance="critico",
                    frame_label="Contrasto",
                    key_claims=["Claim 1", "Claim 2"],
                    evidence_level="alto",
                    orientation_inherited="center-left",
                    orientation_detected="critico",
                    partial=False,
                ),
            )
        ],
    )

    async def _fake_analyze(request: FramesAnalyzeRequest):
        assert request.event_signature == "Summit"
        return fake_response

    monkeypatch.setattr("backend.app.main.analyze_frames", _fake_analyze)

    response = client.post(
        "/v1/frames/analyze",
        json={
            "event_signature": "Summit",
            "per_country_results": [
                {
                    "country": "USA",
                    "items": [
                        {
                            "source": "NYTimes",
                            "domain": "nytimes.com",
                            "url": "https://www.nytimes.com/1",
                            "title": "Titolo",
                            "snippet": "Snippet",
                        }
                    ],
                }
            ],
            "resolved_sources": [
                {
                    "country": "USA",
                    "source": "NYTimes",
                    "orientation": "center-left",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frames"][0]["frame_card"]["tone"] == "analitico"


def test_frames_analyze_handles_service_error(monkeypatch, client):
    async def _failing(_: FramesAnalyzeRequest):
        raise FrameAnalysisServiceError("boom")

    monkeypatch.setattr("backend.app.main.analyze_frames", _failing)

    response = client.post(
        "/v1/frames/analyze",
        json={
            "event_signature": "Summit",
            "per_country_results": [],
            "resolved_sources": [],
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "boom"
