# OpenGPT2
RAG based system
- Reads and indexes local files using FAISS
- Uses sentence transformer as the embedding model
- Uses Flan-T5 LLM for generation
- Uses FastApi to provide a query endpoint
- curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "<Your query>", "top_k": 3}'
