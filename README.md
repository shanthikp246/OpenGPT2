# OpenGPT2
Prereqs:
- copilot installed (brew install aws/tap/copilot-cli)
- jq installed (brew install jq)
- You’ve run aws configure for us-west-2
- Docker is running

RAG based system
- Reads files from S3 and indexes files using FAISS
- Uses sentence transformer as the embedding model
- Uses Flan-T5 LLM for generation
- Uses FastApi to provide a query endpoint

- rag_system subfoler contains a zero-code RAG application
- fine_tune subfolder contains a zero code fine-tuning and inference application
   
