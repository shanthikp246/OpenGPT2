#!/bin/bash

set -e

APP_NAME="squad-gen"
REGION="us-west-2"
ECR_REPO="squad-gen"

echo "Cleaning up AWS Copilot app: $APP_NAME in region: $REGION..."

# Delete Copilot app (this deletes ECS, ALB, CloudWatch, VPC, etc.)
copilot app delete --name "$APP_NAME" --yes

echo "Copilot app deleted."

# Delete ECR repository and all images
echo "Deleting ECR repository: $ECR_REPO"
aws ecr delete-repository --repository-name "$ECR_REPO" --force --region "$REGION"

# Delete IAM role (ecsTaskExecutionRole), if you created it manually
ROLE_NAME="ecsTaskExecutionRole"
echo "Deleting IAM role: $ROLE_NAME"
aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" || true
aws iam delete-role --role-name "$ROLE_NAME" || true

# Optional: delete log groups
echo "Cleaning up CloudWatch log groups..."
LOG_GROUPS=$(aws logs describe-log-groups --region "$REGION" --query "logGroups[?starts_with(logGroupName, '/copilot/$APP_NAME')].logGroupName" --output text)
for log_group in $LOG_GROUPS; do
  echo "Deleting log group: $log_group"
  aws logs delete-log-group --log-group-name "$log_group" --region "$REGION"
done

echo "Cleanup complete ✅"

