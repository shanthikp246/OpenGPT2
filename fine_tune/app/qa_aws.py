# app/qa_aws.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from inference.aws_inference import AwsInference
from app.qa_app_factory import create_app


S3_BUCKET = "opengpt2documents"
# Set up AWS inference pipeline
inference = AwsInference(
    s3_bucket=S3_BUCKET,
    qa_data_path=f"s3://{S3_BUCKET}/qa_pairs.json",
    model_output_dir=f"s3://{S3_BUCKET}/checkpoints/finetuned-model"
)

app = create_app(inference)