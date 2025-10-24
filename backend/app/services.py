import asyncio
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from playwright.async_api import async_playwright

from podcastfy.text_to_speech import TextToSpeech

from .config import get_settings
from .models import GenerationRequest, GenerationResult


@dataclass
class ExtractedContent:
    url: str
    title: str
    summary: str


async def _extract_with_firefox(urls: List[str]) -> List[ExtractedContent]:
    """Use Playwright with Firefox to extract page titles and body text."""

    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        results: List[ExtractedContent] = []
        for url in urls:
            title = ""
            summary = ""
            try:
                await page.goto(url, wait_until="networkidle")
                title = await page.title()
                body_text = await page.inner_text("body")
                cleaned = " ".join(body_text.split())
                summary = textwrap.shorten(cleaned, width=800, placeholder="…")
            except Exception as exc:  # pragma: no cover - network failure
                summary = f"Impossibile estrarre il contenuto: {exc}"
            results.append(ExtractedContent(url=url, title=title or url, summary=summary))
        await browser.close()
    return results


def _build_script(content: ExtractedContent) -> str:
    return (
        f"Question: Cosa racconta l'articolo '{content.title}'?\n"
        f"Answer: {content.summary}"
    )


async def _convert_to_audio(tts: TextToSpeech, script: str, filename: Path) -> None:
    await asyncio.to_thread(tts.convert_to_speech, script, str(filename))


def _build_filename() -> Path:
    settings = get_settings()
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return settings.static_dir / f"gemini_flash_{timestamp}_{unique_id}.mp3"


async def generate_audio(request: GenerationRequest) -> List[GenerationResult]:
    """Extract content from links and convert them to audio."""

    urls = [str(link) for link in request.links][:10]
    if not urls:
        return []

    extracted = await _extract_with_firefox(urls)
    results: List[GenerationResult] = []
    settings = get_settings()
    provider_config = {
        "text_to_speech": {
            "gemini_flash_tts": {
                "model": settings.gemini_model,
                "default_voices": {
                    "question": request.voice or "it-IT-Standard-A",
                    "answer": request.voice or "it-IT-Standard-B",
                },
                "modalities": ["audio"],
                "audioConfig": {"format": "pcm16", "speakingRate": 1.0},
                "generationConfig": {
                    "temperature": 1.0,
                    "topP": 0.9,
                    "topK": 40,
                    "candidateCount": 1,
                },
                "thinkingConfig": {"budgetTokens": 0},
                "responseMimeType": "audio/mp3",
            }
        }
    }
    tts = TextToSpeech(
        model="gemini_flash_tts",
        api_key=settings.gemini_api_key,
        conversation_config=provider_config,
    )
    for item in extracted:
        filename = _build_filename()
        await _convert_to_audio(tts, _build_script(item), filename)
        relative_url = f"/static/{filename.name}"
        results.append(
            GenerationResult(
                url=item.url,
                title=item.title,
                summary=item.summary,
                audio_url=relative_url,
                audio_path=filename,
            )
        )
    return results
