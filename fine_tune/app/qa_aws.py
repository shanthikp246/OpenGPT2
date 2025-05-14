# app/qa_aws.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.aws_inference import AwsInference

app = FastAPI()

# FastAPI schema and route
class QARequest(BaseModel):
    question: str
    context: str

# Set up AWS inference pipeline
inference = AwsInference(
    s3_bucket_name="your-s3-bucket-name",
    qa_data_path="s3://your-s3-bucket-name/qa_pairs.json",
    model_output_dir="s3://your-s3-bucket-name/checkpoints"
)

inference.initialize()

@app.post("/fine-tune-query")
def answer_question(payload: QARequest):
    if not inference.is_ready():
        raise HTTPException(status_code=503, detail="Inference model not available.")

    answer, score = inference.generate(payload.question, payload.context)
    return {"answer": answer, "score": score}

