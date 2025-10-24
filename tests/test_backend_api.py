from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models import GenerationRequest, GenerationResult


@pytest.fixture
def client():
    return TestClient(app)


def test_healthcheck(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_endpoint(monkeypatch, client):
    fake_result = GenerationResult(
        url="https://example.com",
        title="Example",
        summary="Example summary",
        audio_url="/static/audio.mp3",
        audio_path=Path("backend/static/audio.mp3"),
    )

    async_mock = AsyncMock(return_value=[fake_result])
    monkeypatch.setattr("backend.app.main.generate_audio", async_mock)

    response = client.post("/api/generate", json={"links": ["https://example.com"]})
    assert response.status_code == 200

    payload = response.json()
    assert payload["results"][0]["audio_url"] == fake_result.audio_url
    async_mock.assert_awaited_once_with(GenerationRequest(links=["https://example.com"], voice=None))
