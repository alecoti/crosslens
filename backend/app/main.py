from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .models import GenerationRequest, GenerationResponse
from .services import generate_audio

settings = get_settings()

app = FastAPI(title="Podcastfy Gemini Flash Boilerplate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.post("/api/generate", response_model=GenerationResponse)
async def post_generate(request: GenerationRequest) -> JSONResponse:
    try:
        results = await generate_audio(request)
        return JSONResponse(content=GenerationResponse(results=results).model_dump())
    except Exception as exc:  # pragma: no cover - runtime failures
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
