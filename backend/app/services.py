"""Service layer for interacting with OpenAI to build the CrossLens flows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, List, Protocol

from openai import AsyncOpenAI

from .config import get_settings
from .models import (
    ArticleFrame,
    ContextBuildRequest,
    ContextBuildResponse,
    FrameCard,
    FramesAnalyzeRequest,
    FramesAnalyzeResponse,
    ResolvedSource,
)

# ---------------------------------------------------------------------------
# Step 1 - Context Builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Sei un analista che prepara il contesto iniziale per CrossLens, un podcast che confronta la "
    "copertura giornalistica internazionale di uno stesso evento. Devi restituire esclusivamente JSON "
    "valido conforme allo schema fornito. Identifica nazioni coinvolte (ISO-3166 alpha-3), attori (persone), "
    "organizzazioni, categoria tematica dell'evento e un event_signature conciso adatto alla ricerca. "
    "Se l'informazione non è disponibile, usa una lista vuota oppure una stringa vuota. Non aggiungere testo "
    "fuori dal JSON."
)

_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "crosslens_context_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "nations_involved": {
                "type": "array",
                "items": {"type": "string", "pattern": "^[A-Z]{3}$"},
                "description": "ISO-3166 alpha-3 country codes involved in the event",
            },
            "actors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "People directly involved in the event",
            },
            "organizations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Organisations or institutions involved",
            },
            "topic_category": {
                "type": "string",
                "description": "High level topic classification for the news event",
            },
            "event_signature": {
                "type": "string",
                "description": "Short event signature to drive subsequent search",
            },
        },
        "required": [
            "nations_involved",
            "actors",
            "organizations",
            "topic_category",
            "event_signature",
        ],
    },
}


class ContextBuildServiceError(RuntimeError):
    """Raised when the context build flow cannot be completed."""


def _normalise_query(raw_query: str) -> str:
    normalised = " ".join(raw_query.strip().split())
    if not normalised:
        raise ValueError("Query cannot be empty after normalisation")
    return normalised


def _prepare_lists(values: Iterable[str], *, uppercase: bool = False) -> List[str]:
    cleaned: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        if uppercase:
            item = item.upper()
        cleaned.append(item)
    return cleaned


def _extract_payload(raw_output: Any) -> dict[str, Any]:
    if raw_output is None:
        raise ContextBuildServiceError("OpenAI response was empty")
    if isinstance(raw_output, str):
        return json.loads(raw_output)
    if hasattr(raw_output, "output_text"):
        return json.loads(raw_output.output_text)
    # Fallback for objects shaped like the official client response
    try:
        first_output = raw_output.output[0]
        first_content = first_output.content[0]
        text_value = first_content.text  # type: ignore[attr-defined]
    except (AttributeError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
        raise ContextBuildServiceError("Unable to parse OpenAI response payload") from exc
    return json.loads(text_value)


async def _invoke_model(query: str, client: AsyncOpenAI | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ContextBuildServiceError("OpenAI API key not configured")

    api_client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    response = await api_client.responses.create(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
    )
    return _extract_payload(response)


async def build_context(
    request: ContextBuildRequest,
    *,
    client: AsyncOpenAI | None = None,
) -> ContextBuildResponse:
    """Normalise the query and call OpenAI to extract structured context."""

    normalised_query = _normalise_query(request.query)
    payload = await _invoke_model(normalised_query, client=client)

    nations = _prepare_lists(payload.get("nations_involved", []), uppercase=True)
    actors = _prepare_lists(payload.get("actors", []))
    organisations = _prepare_lists(payload.get("organizations", []))
    topic_category = payload.get("topic_category", "").strip()
    event_signature = payload.get("event_signature", "").strip()

    if not topic_category or not event_signature:
        raise ContextBuildServiceError("Model response missing required fields")

    return ContextBuildResponse(
        normalized_query=normalised_query,
        nations_involved=nations,
        actors=actors,
        organizations=organisations,
        topic_category=topic_category,
        event_signature=event_signature,
    )


# ---------------------------------------------------------------------------
# Step 3 - Frame Analysis
# ---------------------------------------------------------------------------

_FRAME_SYSTEM_PROMPT = (
    "Agisci come media analyst per CrossLens. Riceverai informazioni su un articolo di giornale "
    "includendo paese, testata, orientamento noto, titolo, snippet di ricerca e testo estratto. "
    "Il tuo compito è sintetizzare UNA sola Frame Card che descriva tono, stance, frame label, key claims "
    "(2-5 punti sintetici), livello di evidenza e un'eventuale orientazione rilevata. Restituisci esclusivamente "
    "JSON valido conforme allo schema. Se il testo fornito è parziale, rispetta il campo partial passato nel prompt."
)

_FRAME_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "crosslens_frame_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "tone": {"type": "string"},
            "stance": {"type": "string"},
            "frame_label": {"type": "string"},
            "key_claims": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
            },
            "evidence_level": {"type": "string"},
            "orientation_inherited": {"type": ["string", "null"]},
            "orientation_detected": {"type": ["string", "null"]},
            "partial": {"type": "boolean"},
        },
        "required": [
            "tone",
            "stance",
            "frame_label",
            "key_claims",
            "evidence_level",
            "partial",
        ],
    },
}


class ArticleExtractionError(RuntimeError):
    """Raised when article text cannot be extracted."""


class FrameAnalysisServiceError(RuntimeError):
    """Raised when the frame analysis flow fails."""


@dataclass
class ArticleExtraction:
    text: str
    partial: bool = False


class ArticleExtractor(Protocol):
    async def extract(self, url: str) -> ArticleExtraction:  # pragma: no cover - protocol definition
        ...


class PlaywrightArticleExtractor:
    """Extract article text using Playwright with Firefox and Readability parsing."""

    def __init__(self, *, timeout_ms: int = 30_000):
        self.timeout_ms = timeout_ms

    async def extract(self, url: str) -> ArticleExtraction:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - environment guard
            raise ArticleExtractionError("Playwright is not installed") from exc

        try:
            from readability import Document
        except ImportError as exc:  # pragma: no cover - environment guard
            raise ArticleExtractionError("readability-lxml is required for extraction") from exc

        from bs4 import BeautifulSoup

        try:
            async with async_playwright() as playwright:
                browser = await playwright.firefox.launch(headless=True)
                try:
                    page = await browser.new_page()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    except PlaywrightTimeoutError as exc:
                        raise ArticleExtractionError("Timeout while loading article") from exc
                    html = await page.content()
                finally:
                    await browser.close()
        except ArticleExtractionError:
            raise
        except Exception as exc:  # pragma: no cover - network/runtime guard
            raise ArticleExtractionError("Failed to load article content") from exc

        document = Document(html)
        summary_html = document.summary()
        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text("\n", strip=True)

        if not text:
            raise ArticleExtractionError("Article body could not be extracted")

        return ArticleExtraction(text=text, partial=False)


def _build_orientation_map(resolved_sources: Iterable[ResolvedSource]) -> dict[tuple[str, str], str]:
    orientation_map: dict[tuple[str, str], str] = {}
    for source in resolved_sources:
        key = (source.country.upper(), source.source.lower())
        orientation_map[key] = source.orientation
    return orientation_map


def _build_frame_prompt(
    *,
    event_signature: str,
    country: str,
    source: str,
    domain: str,
    title: str,
    snippet: str,
    body: str,
    orientation_inherited: str | None,
    partial: bool,
) -> str:
    orientation_line = orientation_inherited or "non disponibile"
    lines = [
        f"Event signature: {event_signature}",
        f"Country: {country}",
        f"Source: {source} ({domain})",
        f"Orientation inherited: {orientation_line}",
        f"Content completeness: {'parziale' if partial else 'completo'}",
        "",
        "Titolo:",
        title.strip(),
        "",
        "Snippet:",
        snippet.strip(),
        "",
        "Contenuto da analizzare:",
        body.strip(),
    ]
    return "\n".join(lines)


def _clean_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise FrameAnalysisServiceError(f"Model response missing field '{key}'")
    cleaned = value.strip()
    if not cleaned:
        raise FrameAnalysisServiceError(f"Model response provided empty field '{key}'")
    return cleaned


async def _invoke_frame_model(prompt: str, client: AsyncOpenAI | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise FrameAnalysisServiceError("OpenAI API key not configured")

    api_client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    response = await api_client.responses.create(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _FRAME_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_schema", "json_schema": _FRAME_RESPONSE_SCHEMA},
    )
    payload = _extract_payload(response)
    if not isinstance(payload, dict):
        raise FrameAnalysisServiceError("Model response payload was not a JSON object")
    return payload


async def analyze_frames(
    request: FramesAnalyzeRequest,
    *,
    client: AsyncOpenAI | None = None,
    extractor: ArticleExtractor | None = None,
) -> FramesAnalyzeResponse:
    """Extract article bodies and request frame cards for each search result."""

    if not request.event_signature:
        raise FrameAnalysisServiceError("Event signature is required")

    orientation_map = _build_orientation_map(request.resolved_sources)
    active_extractor = extractor or PlaywrightArticleExtractor()

    frames: List[ArticleFrame] = []

    for country_block in request.per_country_results:
        country = country_block.country
        for item in country_block.items:
            orientation_inherited = orientation_map.get((country.upper(), item.source.lower()))
            extracted_text = None
            extraction_partial = False

            if active_extractor is not None:
                try:
                    extraction = await active_extractor.extract(str(item.url))
                    extracted_text = extraction.text.strip() or None
                    extraction_partial = extraction.partial
                except ArticleExtractionError:
                    extracted_text = None
                    extraction_partial = True

            analysis_body = extracted_text or f"{item.title}\n\n{item.snippet}".strip()
            partial_flag = extraction_partial or extracted_text is None

            prompt = _build_frame_prompt(
                event_signature=request.event_signature,
                country=country,
                source=item.source,
                domain=item.domain,
                title=item.title,
                snippet=item.snippet,
                body=analysis_body,
                orientation_inherited=orientation_inherited,
                partial=partial_flag,
            )

            payload = await _invoke_frame_model(prompt, client=client)

            tone = _clean_string(payload, "tone")
            stance = _clean_string(payload, "stance")
            frame_label = _clean_string(payload, "frame_label")
            evidence_level = _clean_string(payload, "evidence_level")

            key_claims = _prepare_lists(payload.get("key_claims", []))
            if not key_claims:
                raise FrameAnalysisServiceError("Model response missing key_claims")

            orientation_detected = payload.get("orientation_detected")
            if orientation_detected is not None and not isinstance(orientation_detected, str):
                orientation_detected = str(orientation_detected)
            orientation_detected = orientation_detected.strip() if isinstance(orientation_detected, str) else None

            partial_response = bool(payload.get("partial", False)) or partial_flag

            frame_card = FrameCard(
                tone=tone,
                stance=stance,
                frame_label=frame_label,
                key_claims=key_claims,
                evidence_level=evidence_level,
                orientation_inherited=orientation_inherited or payload.get("orientation_inherited"),
                orientation_detected=orientation_detected,
                partial=partial_response,
            )

            frames.append(
                ArticleFrame(
                    country=country,
                    source=item.source,
                    domain=item.domain,
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    extracted_text=extracted_text,
                    frame_card=frame_card,
                )
            )

    return FramesAnalyzeResponse(event_signature=request.event_signature, frames=frames)
