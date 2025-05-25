# app/qa_aws.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.aws_inference import AwsInference
from threading import Thread
import asyncio

app = FastAPI()

# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str

S3_BUCKET = "opengpt2documents"
# Set up AWS inference pipeline
inference = AwsInference(
    s3_bucket=S3_BUCKET,
    qa_data_path=f"s3://{S3_BUCKET}/qa_pairs.json",
    model_output_dir=f"s3://{S3_BUCKET}/checkpoints/finetuned-model"
)


@app.on_event("startup")
async def startup_event():
    # Run the blocking initialize() in a background thread without blocking the event loop
    await asyncio.to_thread(inference.initialize)

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



