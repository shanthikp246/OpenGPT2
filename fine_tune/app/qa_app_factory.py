# app/qa_local.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.base import BaseInference
from threading import Thread

app = FastAPI()

# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str

def create_app(inference: BaseInference):
    app = FastAPI()

    @app.on_event("startup")
    def startup_event():
        # Run initialize in a background thread so the server remains responsive
        def background_init():
            try:
                inference.initialize()
            except Exception as e:
                print(f"🔥 Error during initialization: {e}")
    
        Thread(target=background_init, daemon=True).start()

    @app.post("/query")
    def answer_question(payload: QARequest):
        if not inference.is_ready():
            raise HTTPException(status_code=503, detail="Inference model not available.")
    
        answer, score = inference.generate(payload.question, payload.context)
        return {"answer": answer, "score": score}

    @app.get("/status")
    def get_status():
        return inference.get_status()

    @app.get("/")
    def root():
        return {"message": "Fine-tune API is running."}
    
    return app
