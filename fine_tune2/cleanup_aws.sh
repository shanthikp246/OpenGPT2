#!/bin/bash

# AWS Cleanup Script
# This script removes all resources created for the squad-gen-app deployment
# WARNING: This will permanently delete resources and cannot be undone!

set -e

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="021891583393"
CLUSTER_NAME="squad-gen-app-cluster"
SERVICE_NAME="squad-gen-app-service"
TASK_DEFINITION_FAMILY="squad-gen-app-task"
ECR_REPO_NAME="squad-gen-app-repo"  # Update this to your actual ECR repo name
S3_BUCKET_NAME="opengpt2documents"
SECURITY_GROUP_ID="sg-0827438f8713e6bac"
VPC_ID="vpc-067cf2352e5ee2d3b"

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

confirm_deletion() {
    echo_warn "This script will DELETE the following AWS resources:"
    echo "  • ECS Service: $SERVICE_NAME"
    echo "  • ECS Cluster: $CLUSTER_NAME"
    echo "  • ECS Task Definition: $TASK_DEFINITION_FAMILY"
    echo "  • ECR Repository: $ECR_REPO_NAME (and all images)"
    echo "  • CloudWatch Log Groups"
    echo "  • Security Group: $SECURITY_GROUP_ID"
    echo "  • IAM Roles (if created by this deployment)"
    echo ""
    echo_info "S3 Bucket ($S3_BUCKET_NAME) will be left intact."
    echo ""
    echo_warn "This action is IRREVERSIBLE!"
    echo ""
    read -p "Are you sure you want to proceed? (type 'yes' to confirm): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        echo_info "Cleanup cancelled."
        exit 0
    fi
}

# Function to delete ECS service
delete_ecs_service() {
    echo_info "Checking ECS service..."
    
    if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo_info "Scaling down ECS service to 0..."
        aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --desired-count 0 --region $AWS_REGION >/dev/null
        
        echo_info "Waiting for tasks to stop..."
        aws ecs wait services-stable --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION
        
        echo_info "Deleting ECS service..."
        aws ecs delete-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --region $AWS_REGION >/dev/null
        echo_info "✓ ECS service deleted"
    else
        echo_info "ECS service not found or already deleted"
    fi
}

# Function to delete ECS cluster
delete_ecs_cluster() {
    echo_info "Deleting ECS cluster..."
    
    if aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        aws ecs delete-cluster --cluster $CLUSTER_NAME --region $AWS_REGION >/dev/null
        echo_info "✓ ECS cluster deleted"
    else
        echo_info "ECS cluster not found or already deleted"
    fi
}

# Function to deregister task definitions
delete_task_definitions() {
    echo_info "Deregistering task definitions..."
    
    # Get all revisions of the task definition
    TASK_ARNS=$(aws ecs list-task-definitions --family-prefix $TASK_DEFINITION_FAMILY --region $AWS_REGION --query 'taskDefinitionArns[]' --output text 2>/dev/null || echo "")
    
    if [ -n "$TASK_ARNS" ]; then
        for TASK_ARN in $TASK_ARNS; do
            echo_info "Deregistering task definition: $TASK_ARN"
            aws ecs deregister-task-definition --task-definition $TASK_ARN --region $AWS_REGION >/dev/null
        done
        echo_info "✓ Task definitions deregistered"
    else
        echo_info "No task definitions found"
    fi
}

# Function to delete ECR repository
delete_ecr_repository() {
    echo_info "Deleting ECR repository..."
    
    if aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION >/dev/null 2>&1; then
        # Delete all images first
        aws ecr batch-delete-image --repository-name $ECR_REPO_NAME --image-ids "$(aws ecr list-images --repository-name $ECR_REPO_NAME --region $AWS_REGION --query 'imageIds[*]' --output json)" --region $AWS_REGION >/dev/null 2>&1 || true
        
        # Delete repository
        aws ecr delete-repository --repository-name $ECR_REPO_NAME --force --region $AWS_REGION >/dev/null
        echo_info "✓ ECR repository deleted"
    else
        echo_info "ECR repository not found or already deleted"
    fi
}

# Function to preserve S3 bucket
preserve_s3_bucket() {
    echo_info "Checking S3 bucket status..."
    
    if aws s3api head-bucket --bucket $S3_BUCKET_NAME --region $AWS_REGION 2>/dev/null; then
        echo_info "✓ S3 bucket ($S3_BUCKET_NAME) preserved and left intact"
    else
        echo_info "S3 bucket not found - nothing to preserve"
    fi
}

# Function to delete CloudWatch log groups
delete_cloudwatch_logs() {
    echo_info "Deleting CloudWatch log groups..."
    
    # Common log group patterns for ECS
    LOG_GROUPS=(
        "/ecs/squad-gen-app"
        "/aws/ecs/containerinsights/$CLUSTER_NAME/performance"
        "/ecs/$TASK_DEFINITION_FAMILY"
    )
    
    for LOG_GROUP in "${LOG_GROUPS[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $AWS_REGION --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
            aws logs delete-log-group --log-group-name "$LOG_GROUP" --region $AWS_REGION 2>/dev/null || true
            echo_info "✓ Deleted log group: $LOG_GROUP"
        fi
    done
}

# Function to delete security group (optional - be careful with this)
delete_security_group() {
    echo_info "Checking security group..."
    
    # Only delete if it's not the default security group and has our specific ID
    if [ "$SECURITY_GROUP_ID" != "sg-default" ] && aws ec2 describe-security-groups --group-ids $SECURITY_GROUP_ID --region $AWS_REGION >/dev/null 2>&1; then
        echo_warn "Security group found: $SECURITY_GROUP_ID"
        echo_warn "⚠️  Skipping security group deletion for safety"
        echo_warn "   If you created this security group specifically for this app, you can delete it manually:"
        echo_warn "   aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID --region $AWS_REGION"
    else
        echo_info "Security group not found or is default security group"
    fi
}

# Function to delete IAM roles (be very careful with this)
delete_iam_roles() {
    echo_info "Checking IAM roles..."
    
    # Common ECS task and execution role patterns
    ROLE_PATTERNS=(
        "squad-gen-app-task-role"
        "squad-gen-app-execution-role"
        "ecsTaskExecutionRole-squad-gen-app"
    )
    
    for ROLE_PATTERN in "${ROLE_PATTERNS[@]}"; do
        if aws iam get-role --role-name "$ROLE_PATTERN" >/dev/null 2>&1; then
            echo_warn "Found IAM role: $ROLE_PATTERN"
            echo_warn "⚠️  Skipping IAM role deletion for safety"
            echo_warn "   Review and delete manually if created specifically for this app:"
            echo_warn "   aws iam delete-role --role-name $ROLE_PATTERN"
        fi
    done
}

# Main cleanup function
main() {
    echo_info "Starting AWS resource cleanup for squad-gen-app..."
    echo_info "Region: $AWS_REGION"
    echo_info "Account: $AWS_ACCOUNT_ID"
    echo ""
    
    confirm_deletion
    
    echo_info "Beginning cleanup process..."
    
    # Delete resources in order
    delete_ecs_service
    delete_ecs_cluster
    delete_task_definitions
    delete_ecr_repository
    preserve_s3_bucket     # Changed from delete to preserve
    delete_cloudwatch_logs
    delete_security_group  # Optional/Safe
    delete_iam_roles      # Optional/Safe
    
    echo ""
    echo_info "🎉 Cleanup completed!"
    echo_info "All specified resources have been removed."
    echo_warn "Remember to check your AWS billing dashboard to ensure no unexpected charges."
    echo ""
    echo_info "Resources that were skipped for safety:"
    echo_info "  • Security Groups (delete manually if needed)"
    echo_info "  • IAM Roles (delete manually if created specifically for this app)"
    echo_info "  • VPC and Subnets (typically shared resources)"
}

# Run main function
main
