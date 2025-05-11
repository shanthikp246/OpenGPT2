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
   
rag-api/
│
├── main.py                         # FastAPI app (only endpoints)
├── requirements.txt
├── Dockerfile
│
├── orchestrator/
│   ├── __init__.py
│   ├── orchestrator.py            # Interface
│   └── default_orchestrator.py    # Concrete implementation
│
├── blobstore/
│   ├── __init__.py
│   ├── blobstore.py               # Blobstore interface
│   ├── s3_blobstore.py            # S3 implementation
│   └── local_blobstore.py         # Local implementation
│
├── document_processor/
│   ├── __init__.py
│   ├── processor.py               # Processor interface
│   └── simple_processor.py        # Basic splitter/preprocessor
│
├── embedding/
│   ├── __init__.py
│   ├── embedding.py               # Embedding interface
│   └── sentence_transformer.py    # Implementation using sentence-transformers
│
├── vectordb/
│   ├── __init__.py
│   ├── vectordb.py                # Vector DB interface
│   └── faiss_db.py                # FAISS implementation w/ blobstore
│
├── llm/
│   ├── __init__.py
│   ├── llm.py                     # LLM interface
│   └── flan_t5.py                 # Flan-T5 implementation
│
└── query/
    ├── __init__.py
    └── rag_query_engine.py        # Combines query, retrieve, and generate



