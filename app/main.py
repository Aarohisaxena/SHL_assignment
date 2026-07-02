from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.brain.dialogue import DialogueManager
from app.config import get_settings
from app.models import ChatRequest, ChatResponse, HealthResponse

_manager: DialogueManager | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _manager
    settings = get_settings()
    _manager = DialogueManager(settings)
    yield


app = FastAPI(title="SHL Assessment Advisor", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    settings = get_settings()
    if len(body.messages) > settings.max_turns:
        raise HTTPException(status_code=400, detail=f"Max {settings.max_turns} messages allowed")

    if _manager is None:
        raise HTTPException(status_code=503, detail="Service starting")

    return _manager.respond(body.messages)
