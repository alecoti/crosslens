from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models import (
    ContextBuildRequest,
    ContextBuildResponse,
    FramesAnalyzeRequest,
    FramesAnalyzeResponse,
)
from .services import (
    ContextBuildServiceError,
    FrameAnalysisServiceError,
    analyze_frames,
    build_context,
)

settings = get_settings()

app = FastAPI(title="CrossLens Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/v1/context/build", response_model=ContextBuildResponse)
async def post_context_build(request: ContextBuildRequest) -> JSONResponse:
    try:
        response = await build_context(request)
        return JSONResponse(content=response.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ContextBuildServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/frames/analyze", response_model=FramesAnalyzeResponse)
async def post_frames_analyze(request: FramesAnalyzeRequest) -> JSONResponse:
    try:
        response = await analyze_frames(request)
        return JSONResponse(content=response.model_dump(mode="json"))
    except FrameAnalysisServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
