#!/bin/bash

# AWS Deployment Script for Squad-Gen App
# This script builds Docker image and deploys to AWS ECS with S3 permissions

set -e

# Configuration - Update these variables
APP_NAME="squad-gen-app"
S3_BUCKET_NAME="opengpt2documents"  # Replace with your S3 bucket name
AWS_REGION="us-west-2"  # Replace with your preferred region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="$APP_NAME"
IMAGE_TAG="latest"
CONTAINER_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        echo_error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        echo_error "AWS credentials not configured"
        exit 1
    fi
    
    echo_info "Prerequisites check passed"
}

# Create ECR repository
create_ecr_repo() {
    echo_info "Creating ECR repository..."
    
    aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &> /dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
    
    echo_info "ECR repository ready"
}

# Build and push Docker image
build_and_push_image() {
    echo_info "Building and pushing Docker image..."
    
    # Get ECR login token
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Build image
    docker build --platform linux/amd64 -t $ECR_REPO_NAME:$IMAGE_TAG .
    
    # Tag image for ECR
    docker tag $ECR_REPO_NAME:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG
    
    # Push image
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG
    
    echo_info "Docker image pushed successfully"
}

# Create IAM role for ECS task
create_iam_role() {
    echo_info "Creating IAM role and policies..."
    
    # Task execution role (for ECS to pull image and write logs)
    cat > task-execution-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Task role (for application to access S3)
    cat > task-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # S3 access policy
    cat > s3-access-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::$S3_BUCKET_NAME",
        "arn:aws:s3:::$S3_BUCKET_NAME/*"
      ]
    }
  ]
}
EOF

    # Create execution role
    aws iam create-role --role-name ${APP_NAME}-execution-role --assume-role-policy-document file://task-execution-trust-policy.json 2>/dev/null || echo_warn "Execution role already exists"
    aws iam attach-role-policy --role-name ${APP_NAME}-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    # Create task role
    aws iam create-role --role-name ${APP_NAME}-task-role --assume-role-policy-document file://task-trust-policy.json 2>/dev/null || echo_warn "Task role already exists"
    aws iam put-role-policy --role-name ${APP_NAME}-task-role --policy-name S3AccessPolicy --policy-document file://s3-access-policy.json

    # Clean up policy files
    rm -f task-execution-trust-policy.json task-trust-policy.json s3-access-policy.json
    
    echo_info "IAM roles and policies created"
}

# Create ECS cluster
create_ecs_cluster() {
    echo_info "Creating ECS cluster..."
    
    # Check if cluster exists first
    if aws ecs describe-clusters --clusters $APP_NAME-cluster --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo_warn "Cluster already exists and is active"
    else
        # Create cluster with basic configuration (works with all CLI versions)
        aws ecs create-cluster --cluster-name $APP_NAME-cluster --region $AWS_REGION
        
        # Wait a moment for cluster to be ready
        sleep 5
        
        # Verify cluster was created
        if aws ecs describe-clusters --clusters $APP_NAME-cluster --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
            echo_info "ECS cluster created successfully"
        else
            echo_error "Failed to create ECS cluster"
            exit 1
        fi
    fi
    
    echo_info "ECS cluster ready"
}

# Create task definition
create_task_definition() {
    echo_info "Creating ECS task definition..."
    
    cat > task-definition.json << EOF
{
  "family": "$APP_NAME-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/${APP_NAME}-execution-role",
  "taskRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/${APP_NAME}-task-role",
  "containerDefinitions": [
    {
      "name": "$APP_NAME-container",
      "image": "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG",
      "portMappings": [
        {
          "containerPort": $CONTAINER_PORT,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "S3_BUCKET_NAME",
          "value": "$S3_BUCKET_NAME"
        },
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "$AWS_REGION"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/$APP_NAME",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

    # Create CloudWatch log group
    aws logs create-log-group --log-group-name /ecs/$APP_NAME --region $AWS_REGION 2>/dev/null || echo_warn "Log group already exists"
    
    # Register task definition
    aws ecs register-task-definition --cli-input-json file://task-definition.json --region $AWS_REGION
    
    rm -f task-definition.json
    echo_info "Task definition created"
}

# Get or create VPC and subnets
setup_networking() {
    echo_info "Setting up networking..."
    
    # Get default VPC
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
    
    if [ "$VPC_ID" = "None" ] || [ "$VPC_ID" = "" ]; then
        echo_error "No default VPC found. Please create a VPC first."
        exit 1
    fi
    
    # Get public subnets
    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[?MapPublicIpOnLaunch==`true`].SubnetId' --output text --region $AWS_REGION)
    
    if [ -z "$SUBNET_IDS" ]; then
        echo_error "No public subnets found in default VPC"
        exit 1
    fi
    
    # Convert to comma-separated list
    SUBNET_LIST=$(echo $SUBNET_IDS | tr ' ' ',')
    
    # Create security group
    SG_ID=$(aws ec2 create-security-group \
        --group-name ${APP_NAME}-sg \
        --description "Security group for $APP_NAME" \
        --vpc-id $VPC_ID \
        --query 'GroupId' \
        --output text \
        --region $AWS_REGION 2>/dev/null || \
        aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${APP_NAME}-sg" "Name=vpc-id,Values=$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region $AWS_REGION)
    
    # Add inbound rule for HTTP traffic
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp \
        --port $CONTAINER_PORT \
        --cidr 0.0.0.0/0 \
        --region $AWS_REGION 2>/dev/null || echo_warn "Security group rule already exists"
    
    echo_info "Networking setup complete"
    echo_info "VPC: $VPC_ID"
    echo_info "Subnets: $SUBNET_LIST"
    echo_info "Security Group: $SG_ID"
}

# Create ECS service
create_ecs_service() {
    echo_info "Creating ECS service..."
    
    # Convert subnet list to proper JSON array format
    SUBNET_JSON=$(echo $SUBNET_IDS | tr ' ' '\n' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' -)
    
    cat > service-definition.json << EOF
{
  "serviceName": "$APP_NAME-service",
  "cluster": "$APP_NAME-cluster",
  "taskDefinition": "$APP_NAME-task",
  "desiredCount": 1,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": [$SUBNET_JSON],
      "securityGroups": ["$SG_ID"],
      "assignPublicIp": "ENABLED"
    }
  }
}
EOF

    aws ecs create-service --cli-input-json file://service-definition.json --region $AWS_REGION
    
    rm -f service-definition.json
    echo_info "ECS service created"
}

# Get service information
get_service_info() {
    echo_info "Waiting for service to be running..."
    
    # Wait for service to be stable
    aws ecs wait services-stable --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION
    
    # Get task ARN
    TASK_ARN=$(aws ecs list-tasks --cluster $APP_NAME-cluster --service-name $APP_NAME-service --query 'taskArns[0]' --output text --region $AWS_REGION)
    
    if [ "$TASK_ARN" != "None" ] && [ "$TASK_ARN" != "" ]; then
        # Get public IP
        PUBLIC_IP=$(aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text --region $AWS_REGION | xargs -I {} aws ec2 describe-network-interfaces --network-interface-ids {} --query 'NetworkInterfaces[0].Association.PublicIp' --output text --region $AWS_REGION)
        
        echo_info "Deployment completed successfully!"
        echo_info "Application URL: http://$PUBLIC_IP:$CONTAINER_PORT"
        echo_info "Health check: http://$PUBLIC_IP:$CONTAINER_PORT/health"
        echo_info "Docs: http://$PUBLIC_IP:$CONTAINER_PORT/docs"
    else
        echo_warn "Could not retrieve service information. Check AWS Console for details."
    fi
}

# Main deployment function
main() {
    echo_info "Starting deployment of $APP_NAME..."
    echo_info "Target S3 bucket: $S3_BUCKET_NAME"
    echo_info "AWS Region: $AWS_REGION"
    
    check_prerequisites
    create_ecr_repo
    build_and_push_image
    create_iam_role
    create_ecs_cluster
    create_task_definition
    setup_networking
    create_ecs_service
    get_service_info
    
    echo_info "Deployment process completed!"
}

# Run main function
main "$@"
