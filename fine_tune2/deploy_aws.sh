#!/bin/bash

set -e

APP_NAME="squad-gen"
SERVICE_NAME="api"
ENV_NAME="test"
REGION="us-west-2"
DOCKER_IMAGE="squad-gen"
DOCKERFILE="Dockerfile"
BUCKET_NAME="opengpt2documents"
POLICY_NAME="S3FullAccessToOpenGPT2Documents"

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

# IAM policy JSON content
POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    }
  ]
}
EOF
)

echo "🔐 Ensuring managed policy exists: $POLICY_NAME"

POLICY_ARN=$(aws iam list-policies --scope Local --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" --output text)

if [ -z "$POLICY_ARN" ]; then
  echo "📄 Creating managed policy: $POLICY_NAME"
  POLICY_ARN=$(aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOC" \
    --query 'Policy.Arn' --output text)
else
  echo "✅ Managed policy already exists: $POLICY_ARN"
fi

# Get task role name from Copilot-generated task definition
echo "🔍 Retrieving ECS task role ARN..."
CLUSTER_NAME=$(aws ecs list-clusters --query "clusterArns[?contains(@, '$APP_NAME-$ENV_NAME')]" --output text)
SERVICE_NAME_FULL=$(aws ecs list-services --cluster "$CLUSTER_NAME" --query "serviceArns[?contains(@, '$SERVICE_NAME')]" --output text)
TASK_DEF=$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME_FULL" --query "services[0].taskDefinition" --output text)
TASK_ROLE_ARN=$(aws ecs describe-task-definition --task-definition "$TASK_DEF" --query "taskDefinition.taskRoleArn" --output text)
TASK_ROLE_NAME=$(basename "$TASK_ROLE_ARN")

echo "🔗 Attaching policy $POLICY_NAME to task role: $TASK_ROLE_NAME"
aws iam attach-role-policy --role-name "$TASK_ROLE_NAME" --policy-arn "$POLICY_ARN"

# Show endpoint
echo "🌐 Fetching service endpoint..."
copilot svc show --name "$SERVICE_NAME" --app "$APP_NAME" --json | jq -r '.service.uri'

echo "✅ Deployment complete!"

