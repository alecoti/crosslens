from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class ContextBuildRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User news query to analyse")


class ContextBuildResponse(BaseModel):
    normalized_query: str = Field(..., description="Normalized version of the original query")
    nations_involved: List[str] = Field(
        default_factory=list, description="ISO-3166 alpha-3 country codes"
    )
    actors: List[str] = Field(
        default_factory=list, description="Individuals involved in the news event"
    )
    organizations: List[str] = Field(
        default_factory=list, description="Organizations mentioned in the news event"
    )
    topic_category: str = Field(
        ..., description="High-level topic classification for the news event"
    )
    event_signature: str = Field(
        ..., description="Concise signature describing the event for search queries"
    )


class SearchResultItem(BaseModel):
    source: str = Field(..., description="Short name of the news source")
    domain: str = Field(..., description="Domain name of the news source")
    url: AnyHttpUrl = Field(..., description="Article URL returned by Serper.dev")
    title: str = Field(..., description="Title from the search result")
    snippet: str = Field(..., description="Snippet/summary from the search result")


class SearchCountryResults(BaseModel):
    country: str = Field(..., description="ISO-3166 alpha-3 of the country for the sources")
    items: List[SearchResultItem] = Field(
        default_factory=list, description="Search items returned for the country"
    )


class ResolvedSource(BaseModel):
    country: str = Field(..., description="ISO-3166 alpha-3 country code")
    source: str = Field(..., description="Short name of the news source")
    orientation: str = Field(..., description="Orientation metadata from NEWS_SOURCES_MAP")


class SearchPlanExecuteResponse(BaseModel):
    event_signature: str = Field(..., description="Event signature propagated from Step 1")
    per_country_results: List[SearchCountryResults] = Field(
        default_factory=list,
        description="Results grouped by country with up to three articles per source",
    )
    resolved_sources: List[ResolvedSource] = Field(
        default_factory=list,
        description="Resolved source metadata carrying editorial orientation",
    )


class FramesAnalyzeRequest(SearchPlanExecuteResponse):
    """Input payload for the frame analysis step."""


class FrameCard(BaseModel):
    tone: str = Field(..., description="Tone detected in the article narrative")
    stance: str = Field(..., description="Stance toward the primary actor or thesis")
    frame_label: str = Field(..., description="Concise label for the narrative frame")
    key_claims: List[str] = Field(
        ..., min_length=1, description="Key claims (2-5 bullet-style entries)"
    )
    evidence_level: str = Field(
        ..., description="Level of evidence supporting the claims in the article"
    )
    orientation_inherited: Optional[str] = Field(
        default=None,
        description="Orientation metadata passed from configuration",
    )
    orientation_detected: Optional[str] = Field(
        default=None,
        description="Orientation inferred by the LLM (can differ from inherited)",
    )
    partial: bool = Field(
        default=False,
        description="Whether the analysis was based on incomplete article content",
    )


class ArticleFrame(BaseModel):
    country: str = Field(..., description="ISO-3166 alpha-3 country for the article")
    source: str = Field(..., description="Short name for the source")
    domain: str = Field(..., description="Domain name of the source")
    url: AnyHttpUrl = Field(..., description="URL of the analysed article")
    title: str = Field(..., description="Article title")
    snippet: str = Field(..., description="Search snippet used as fallback context")
    extracted_text: Optional[str] = Field(
        default=None, description="Extracted article text used for analysis"
    )
    frame_card: FrameCard = Field(..., description="Generated frame card for the article")


class FramesAnalyzeResponse(BaseModel):
    event_signature: str = Field(..., description="Event signature propagated downstream")
    frames: List[ArticleFrame] = Field(
        default_factory=list,
        description="Frame cards generated for each analysed article",
    )
