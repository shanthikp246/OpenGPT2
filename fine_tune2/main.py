# main.py
import logging
import os
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from interfaces import *
from implementations import *
from squad_generator import SQuADDatasetGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models
class GenerationRequest(BaseModel):
    bucket_name: str

class GenerationResponse(BaseModel):
    task_id: str
    message: str

class StatusResponse(BaseModel):
    task_id: str
    bucket_name: str
    status: str
    total_files: int
    processed_files: int
    generated_examples: int
    error_message: str = None
    started_at: str = None
    completed_at: str = None

# Initialize FastAPI app
app = FastAPI(
    title="SQuAD Dataset Generator API",
    description="Generate SQuAD-style datasets from documents in S3 buckets",
    version="1.0.0"
)

# Initialize dependencies
blob_store = S3BlobStore(region_name=os.getenv("AWS_REGION", "us-west-2"))
document_extractor = DocumentExtractor()
question_generator = TransformerQuestionGenerator()
status_tracker = InMemoryStatusTracker()

# Initialize generator
generator = SQuADDatasetGenerator(
    blob_store=blob_store,
    document_extractor=document_extractor,
    question_generator=question_generator,
    status_tracker=status_tracker
)

@app.get("/")
async def root():
    return {
        "message": "SQuAD Dataset Generator API",
        "version": "1.0.0",
        "endpoints": {
            "/gen": "POST - Start dataset generation from S3 bucket",
            "/status/{task_id}": "GET - Get generation status",
            "/health": "GET - Health check"
        }
    }

@app.post("/gen", response_model=GenerationResponse)
async def generate_dataset(request: GenerationRequest):
    """
    Start background task to generate SQuAD dataset from S3 bucket
    """
    try:
        logger.info(f"Starting dataset generation for bucket: {request.bucket_name}")
        
        # Validate bucket name
        if not request.bucket_name or not request.bucket_name.strip():
            raise HTTPException(status_code=400, detail="Bucket name cannot be empty")
        
        # Start generation
        task_id = await generator.start_generation(request.bucket_name)
        
        return GenerationResponse(
            task_id=task_id,
            message=f"Dataset generation started for bucket '{request.bucket_name}'. Use /status/{task_id} to check progress."
        )
        
    except Exception as e:
        logger.error(f"Error starting generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start generation: {str(e)}")

@app.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    """
    Get status of dataset generation task
    """
    try:
        status = await generator.get_generation_status(task_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return StatusResponse(
            task_id=status.task_id,
            bucket_name=status.bucket_name,
            status=status.status,
            total_files=status.total_files,
            processed_files=status.processed_files,
            generated_examples=status.generated_examples,
            error_message=status.error_message,
            started_at=status.started_at,
            completed_at=status.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.get("/status")
async def list_all_statuses():
    """
    Get all active generation tasks (debug endpoint)
    """
    try:
        # This is a simple implementation - in production you'd want pagination
        all_statuses = []
        if hasattr(status_tracker, 'statuses'):
            for task_id, status in status_tracker.statuses.items():
                all_statuses.append({
                    "task_id": status.task_id,
                    "bucket_name": status.bucket_name,
                    "status": status.status,
                    "processed_files": status.processed_files,
                    "total_files": status.total_files,
                    "generated_examples": status.generated_examples,
                    "started_at": status.started_at
                })
        
        return {
            "active_tasks": len(all_statuses),
            "tasks": all_statuses
        }
        
    except Exception as e:
        logger.error(f"Error listing statuses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list statuses: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "blob_store": "ok",
            "document_extractor": "ok",
            "question_generator": "ok" if question_generator.qa_pipeline else "error",
            "status_tracker": "ok"
        }
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )