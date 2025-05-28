#!/bin/bash

set -e

APP_NAME="fine-tune"
SERVICE_NAME="api"
ENV_NAME="test2"
REGION="us-west-2"
DOCKER_IMAGE="fine-tune"
DOCKERFILE="Dockerfile.aws"

echo "🔧 Checking for Copilot CLI..."
if ! command -v copilot &> /dev/null; then
  echo "❌ Copilot CLI not found. Install it from https://docs.aws.amazon.com/copilot/latest/userguide/install.html"
  exit 1
fi

echo "🐳 Building Docker image..."
docker build -f "$DOCKERFILE" -t "$DOCKER_IMAGE" .

# Initialize app if not exists
if ! copilot app show --name "$APP_NAME" &> /dev/null; then
  echo "📦 Initializing Copilot app: $APP_NAME"
  copilot app init "$APP_NAME"
fi

# Initialize service if not exists
if ! copilot svc show --name "$SERVICE_NAME" --app "$APP_NAME" &> /dev/null; then
  echo "🚀 Initializing service: $SERVICE_NAME"
  copilot svc init \
    --name "$SERVICE_NAME" \
    --svc-type "Load Balanced Web Service" \
    --dockerfile "./$DOCKERFILE"
fi

# Initialize and deploy environment if not exists
if ! copilot env show --name "$ENV_NAME" &> /dev/null; then
  echo "🌎 Initializing environment: $ENV_NAME"
  copilot env init \
    --name "$ENV_NAME" \
    --profile default 
fi

echo "🛰  Deploying environment: $ENV_NAME"
copilot env deploy --name "$ENV_NAME"

# Deploy service
echo "🚀 Deploying service: $SERVICE_NAME to $ENV_NAME"
copilot svc deploy \
  --name "$SERVICE_NAME" \
  --env "$ENV_NAME" \
  --app "$APP_NAME" 

# Show endpoint
echo "🌐 Fetching service endpoint..."
copilot svc show --name "$SERVICE_NAME" --app "$APP_NAME" --json | jq -r '.service.uri'

echo "✅ Deployment complete!"
