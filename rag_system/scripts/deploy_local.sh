#!/bin/bash
set -e

DOCKER_IMAGE="rag-api"
DOCKERFILE="Dockerfile.local"
echo "🐳 Building Docker image..."
docker build -f "$DOCKERFILE" -t "$DOCKER_IMAGE" .

echo "🚀 Launching FastAPI app on http://127.0.0.1:8000 ..."
uvicorn app.main_local:app --reload --host 127.0.0.1 --port 8000

