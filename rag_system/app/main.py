from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator.local_orchestrator import LocalRAGOrchestrator

app = FastAPI()

# Load orchestrator and initialize
orchestrator = LocalRAGOrchestrator(
    doc_path="./documents",
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
