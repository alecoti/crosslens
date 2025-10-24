from pathlib import Path
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class GenerationRequest(BaseModel):
    links: List[AnyHttpUrl] = Field(..., description="Links to extract content from")
    voice: Optional[str] = Field(None, description="Override default Gemini voice")


class GenerationResult(BaseModel):
    url: AnyHttpUrl
    title: str
    summary: str
    audio_url: str
    audio_path: Path = Field(exclude=True)


class GenerationResponse(BaseModel):
    results: List[GenerationResult]
