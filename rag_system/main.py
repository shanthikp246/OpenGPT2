from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator.default_orchestrator import DefaultRAGOrchestrator

app = FastAPI()

# Load orchestrator and initialize
orchestrator = DefaultRAGOrchestrator(
    s3_bucket="your-s3-bucket",
    s3_prefix="your-data-prefix",
    index_path="vector_index/index.bin"
)
orchestrator.initialize()

class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

@app.post("/query")
async def query_rag(req: QueryRequest):
    try:
        result = orchestrator.query(req.query, req.top_k)
        return {"answer": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
