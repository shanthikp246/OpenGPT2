#!/bin/bash
set -e

# Build the Docker image for local
echo "Building Docker image for local deployment..."
docker build -f Dockerfile.local -t fine-tune-app-local .

# Run the container locally
echo "Running Docker container locally..."
docker run -p 8000:8000 fine-tune-app-local

