# app/qa_aws.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.aws_inference import AwsInference
from threading import Thread

app = FastAPI()

# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str

# Set up AWS inference pipeline
inference = AwsInference(
    s3_bucket="documents",
    qa_data_path="s3://documents/qa_pairs.json",
    model_output_dir="s3://documents/checkpoints/finetuned-model"
)

def background_initialize():
    inference.initialize()

# Kick off background initialization
Thread(target=background_initialize, daemon=True).start()

@app.post("/query")
def answer_question(payload: QARequest):
    if not inference.is_ready():
        raise HTTPException(status_code=503, detail="Inference model not available.")

    answer, score = inference.generate(payload.question, payload.context)
    return {"answer": answer, "score": score}

@app.get("/status")
def get_status():
    return {"status": inference.get_status()}

@app.get("/")
def root():
    return {"message": "Fine-tune API is running."}



