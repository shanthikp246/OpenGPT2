"""Factory utilities for building RAG FastAPI applications."""

from threading import Thread

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..orchestrator.orchestrator import RAGOrchestrator


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


def create_app(orchestrator: RAGOrchestrator) -> FastAPI:
    """Create a FastAPI application backed by the provided orchestrator."""
    app = FastAPI()
    state = {
        "ready": False,
        "error": None,
    }

    def background_initialize() -> None:
        try:
            orchestrator.initialize()
            state["ready"] = True
        except Exception as exc:  # pragma: no cover - surfaced via API status
            state["error"] = str(exc)

    @app.on_event("startup")
    def startup_event() -> None:
        Thread(target=background_initialize, daemon=True).start()

    @app.post("/query")
    async def query_rag(req: QueryRequest):
        if state["error"]:
            raise HTTPException(status_code=500, detail=state["error"])
        if not state["ready"]:
            raise HTTPException(status_code=503, detail="RAG orchestrator is still initializing.")
        result = orchestrator.query(req.query, req.top_k)
        return result

    @app.get("/status")
    async def status():
        return {
            "ready": state["ready"],
            "error": state["error"],
        }

    @app.get("/")
    async def root():
        return {"message": "RAG API is running"}

    return app
