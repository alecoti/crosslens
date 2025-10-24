"""Gemini Flash Preview TTS provider implementation."""

from __future__ import annotations

import base64
import copy
import logging
from typing import Any, Dict, List, Optional

import requests

from ..base import TTSProvider

logger = logging.getLogger(__name__)


class GeminiFlashTTSTTS(TTSProvider):
    """Provider that uses Gemini Flash preview TTS models."""

    API_URL_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    config_key = "gemini_flash_tts"

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-preview-tts"):
        if not api_key:
            raise ValueError("Gemini Flash TTS provider requires an API key")

        self.api_key = api_key
        self.model = model or "gemini-2.5-flash-preview-tts"

    def generate_audio(
        self,
        text: str,
        voice: str,
        model: str,
        voice2: str = None,
        **kwargs: Any,
    ) -> bytes:
        target_model = model or self.model
        self.validate_parameters(text, voice, target_model, voice2=voice2)

        payload = self._build_payload(text, voice, voice2, kwargs)
        timeout = kwargs.get("timeout", 120)

        try:
            response = requests.post(
                self.API_URL_TEMPLATE.format(model=target_model),
                params={"key": self.api_key},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Gemini Flash TTS request failed: %s", exc)
            raise RuntimeError(f"Gemini Flash TTS request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Gemini Flash TTS returned a non-JSON response: %s", exc)
            raise RuntimeError("Gemini Flash TTS returned an unexpected response format") from exc
        if isinstance(data, dict) and "error" in data:
            error_message = data.get("error", {}).get("message", "Unknown error")
            logger.error("Gemini Flash TTS returned an error: %s", data.get("error"))
            raise RuntimeError(
                f"Gemini Flash TTS returned an error: {error_message}"
            )

        audio_bytes = self._extract_audio_bytes(data)
        if not audio_bytes:
            raise RuntimeError("Gemini Flash TTS response did not include audio data")

        return audio_bytes

    def _build_payload(
        self,
        text: str,
        voice: str,
        voice2: Optional[str],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": text}],
                }
            ]
        }

        modalities = options.get("modalities") or options.get("Modalities")
        resolved_modalities = modalities or ["audio"]
        if isinstance(resolved_modalities, list):
            payload["modalities"] = [str(mod).upper() for mod in resolved_modalities]
        else:
            payload["modalities"] = [str(resolved_modalities).upper()]

        audio_config = self._copy_config(options, "audio_config", "audioConfig")
        if audio_config is None:
            audio_config = {}
        if isinstance(audio_config, dict):
            audio_config = copy.deepcopy(audio_config)
            audio_config.setdefault("voice", voice)
            if voice2 and "secondaryVoice" not in audio_config and "voices" not in audio_config:
                audio_config["secondaryVoice"] = voice2
        payload["audioConfig"] = audio_config

        generation_config = self._copy_config(
            options, "generation_config", "generationConfig"
        )
        if generation_config is not None:
            payload["generationConfig"] = generation_config

        safety_settings = self._copy_config(
            options, "safety_settings", "safetySettings"
        )
        if safety_settings is not None:
            payload["safetySettings"] = safety_settings

        thinking_config = self._copy_config(
            options, "thinking_config", "thinkingConfig"
        )
        if thinking_config is not None:
            payload["thinkingConfig"] = thinking_config

        request_options = self._copy_config(
            options, "request_options", "requestOptions"
        )
        if request_options is not None:
            payload["requestOptions"] = request_options

        response_mime_type = options.get("response_mime_type") or options.get(
            "responseMimeType"
        )
        if response_mime_type:
            payload["responseMimeType"] = response_mime_type

        return payload

    @staticmethod
    def _copy_config(options: Dict[str, Any], *keys: str) -> Optional[Any]:
        for key in keys:
            if key in options and options[key] is not None:
                return copy.deepcopy(options[key])
        return None

    def _extract_audio_bytes(self, data: Dict[str, Any]) -> bytes:
        candidates: List[Dict[str, Any]] = data.get("candidates", []) if isinstance(data, dict) else []
        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            for part in parts:
                inline_data = part.get("inlineData")
                if not inline_data:
                    continue
                audio_data = inline_data.get("data")
                if not audio_data:
                    continue
                try:
                    return base64.b64decode(audio_data)
                except (ValueError, TypeError) as exc:
                    logger.error("Invalid audio data returned by Gemini Flash TTS: %s", exc)
                    raise RuntimeError("Gemini Flash TTS returned invalid audio data") from exc
        return b""

