# app/qa_local.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..inference.base import BaseInference
from threading import Thread


# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str


def create_app(inference: BaseInference, auto_initialize: bool = True):
    app = FastAPI()
    state = {"started": False}

    def trigger_initialization():
        if state["started"]:
            return
        state["started"] = True

        def background_init():
            try:
                inference.initialize()
            except Exception as e:
                print(f"🔥 Error during initialization: {e}")
                state["started"] = False

        Thread(target=background_init, daemon=True).start()

    if auto_initialize:
        @app.on_event("startup")
        def startup_event():
            trigger_initialization()

    @app.post("/query")
    def answer_question(payload: QARequest):
        if not inference.is_ready():
            raise HTTPException(status_code=503, detail="Inference model not available.")

        answer, score = inference.generate(payload.question, payload.context)
        return {"answer": answer, "score": score}

    @app.post("/initialize")
    def manual_initialize():
        trigger_initialization()
        return {"status": inference.get_status()}

    @app.get("/status")
    def get_status():
        return inference.get_status()

    @app.get("/")
    def root():
        return {"message": "Fine-tune API is running."}
    
    return app
