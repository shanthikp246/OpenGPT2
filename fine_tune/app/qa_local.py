# app/qa_local.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.qa_app_factory import create_app
from inference.local_inference import LocalInference


# Set up local inference pipeline
inference = LocalInference(
    documents_path="./documents",
    qa_data_path="./checkpoints/qa_pairs.json",
    model_output_dir="./checkpoints"
)

app = create_app(inference)
