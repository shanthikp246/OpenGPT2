# app/qa_local.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.local_inference import LocalInference

app = FastAPI()

# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str

# Set up local inference pipeline
inference = LocalInference(
    documents_path="./documents",
    qa_data_path="./checkpoints/qa_pairs.json",
    model_output_dir="./checkpoints"
)

inference.initialize()

@app.post("/fine-tune-query")
def answer_question(payload: QARequest):
    if not inference.is_ready():
        raise HTTPException(status_code=503, detail="Inference model not available.")

    answer, score = inference.generate(payload.question, payload.context)
    return {"answer": answer, "score": score}

