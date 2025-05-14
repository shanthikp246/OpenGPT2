#!/bin/bash
set -e

# Build the Docker image for AWS
echo "Building Docker image for AWS deployment..."
docker build -f Dockerfile.aws -t fine-tune-app-aws .

# Initialize Copilot app and deploy
echo "Deploying with Copilot..."
copilot init --app fine-tune-app --svc fine-tune-api --type "Load Balanced Web Service" --dockerfile "./Dockerfile.aws" --port 8000 || true
copilot deploy --name fine-tune-api --env test

