import base64

import pytest

from podcastfy.tts.providers.gemini_flash_tts import GeminiFlashTTSTTS


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError

            raise HTTPError(f"Status {self.status_code}")

    def json(self):
        return self._payload


def test_gemini_flash_tts_generates_payload(monkeypatch):
    provider = GeminiFlashTTSTTS(api_key="secret")
    captured = {}

    audio_bytes = base64.b64encode(b"audio-bytes").decode()

    def fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            payload={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/mp3",
                                        "data": audio_bytes,
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "podcastfy.tts.providers.gemini_flash_tts.requests.post", fake_post
    )

    audio = provider.generate_audio(
        "Ciao",
        voice="it-IT-Standard-A",
        model="gemini-2.5-flash-preview-tts",
        modalities=["audio"],
        audioConfig={"format": "pcm16"},
        generationConfig={"temperature": 0.9},
    )

    assert captured["params"]["key"] == "secret"
    assert captured["json"]["audioConfig"]["voice"] == "it-IT-Standard-A"
    assert captured["json"]["modalities"] == ["AUDIO"]
    assert captured["json"]["generationConfig"] == {"temperature": 0.9}
    assert audio == b"audio-bytes"


def test_gemini_flash_tts_raises_without_audio(monkeypatch):
    provider = GeminiFlashTTSTTS(api_key="secret")

    monkeypatch.setattr(
        "podcastfy.tts.providers.gemini_flash_tts.requests.post",
        lambda *_, **__: DummyResponse(payload={"candidates": []}),
    )

    with pytest.raises(RuntimeError):
        provider.generate_audio(
            "Hello", voice="it-IT-Standard-A", model="gemini-2.5-flash-preview-tts"
        )


def test_gemini_flash_tts_propagates_http_error(monkeypatch):
    provider = GeminiFlashTTSTTS(api_key="secret")

    def failing_post(*_, **__):
        response = DummyResponse(status_code=500)

        def raise_error():
            from requests import HTTPError

            raise HTTPError("Server error")

        response.raise_for_status = raise_error
        return response

    monkeypatch.setattr(
        "podcastfy.tts.providers.gemini_flash_tts.requests.post", failing_post
    )

    with pytest.raises(RuntimeError):
        provider.generate_audio(
            "Hello", voice="it-IT-Standard-A", model="gemini-2.5-flash-preview-tts"
        )
