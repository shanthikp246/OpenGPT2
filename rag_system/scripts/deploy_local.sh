#!/bin/bash
set -e

DOCKER_IMAGE="rag-api"
echo "🐳 Building Docker image..."
docker build -t "$DOCKER_IMAGE" .

echo "🚀 Launching FastAPI app on http://127.0.0.1:8000 ..."
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

