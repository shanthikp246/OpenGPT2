#!/bin/bash

# Script to fix ECS service creation
set -e

APP_NAME="squad-gen-app"
AWS_REGION="us-west-2"  # Update if you used a different region
CONTAINER_PORT=8000

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Check if resources exist
check_resources() {
    echo_info "Checking existing resources..."
    
    # Check cluster
    if ! aws ecs describe-clusters --clusters $APP_NAME-cluster --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo_error "Cluster $APP_NAME-cluster not found or not active"
        exit 1
    fi
    echo_info "✓ Cluster exists and is active"
    
    # Check task definition
    if ! aws ecs describe-task-definition --task-definition $APP_NAME-task --region $AWS_REGION &>/dev/null; then
        echo_error "Task definition $APP_NAME-task not found"
        exit 1
    fi
    echo_info "✓ Task definition exists"
    
    # Get networking info
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[?MapPublicIpOnLaunch==`true`].SubnetId' --output text --region $AWS_REGION)
    SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${APP_NAME}-sg" "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[0].GroupId' --output text --region $AWS_REGION)
    
    if [ -z "$SUBNET_IDS" ] || [ "$SG_ID" = "None" ]; then
        echo_error "Required networking resources not found"
        exit 1
    fi
    
    echo_info "✓ Networking resources found"
    echo_info "VPC: $VPC_ID"
    echo_info "Security Group: $SG_ID"
    echo_info "Subnets: $SUBNET_IDS"
}

# Delete existing service if it exists but is not working
cleanup_service() {
    echo_info "Checking for existing service..."
    
    if aws ecs describe-services --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION &>/dev/null; then
        echo_warn "Found existing service, checking status..."
        SERVICE_STATUS=$(aws ecs describe-services --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION --query 'services[0].status' --output text)
        
        if [ "$SERVICE_STATUS" = "DRAINING" ] || [ "$SERVICE_STATUS" = "INACTIVE" ]; then
            echo_warn "Service is in $SERVICE_STATUS state, will delete it"
            aws ecs delete-service --cluster $APP_NAME-cluster --service $APP_NAME-service --region $AWS_REGION --force
            echo_info "Waiting for service to be deleted..."
            aws ecs wait services-inactive --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION
        elif [ "$SERVICE_STATUS" = "ACTIVE" ]; then
            echo_info "Service is active, will update it instead"
            return 0
        fi
    fi
}

# Create ECS service
create_service() {
    echo_info "Creating ECS service..."
    
    # Convert subnet IDs to JSON array format
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
  },
  "enableExecuteCommand": true
}
EOF

    echo_info "Service definition:"
    cat service-definition.json
    
    # Create the service
    if aws ecs create-service --cli-input-json file://service-definition.json --region $AWS_REGION; then
        echo_info "Service created successfully"
        rm -f service-definition.json
        return 0
    else
        echo_error "Failed to create service"
        echo_info "Service definition was:"
        cat service-definition.json
        rm -f service-definition.json
        return 1
    fi
}

# Wait for service to be stable and get info
wait_and_get_info() {
    echo_info "Waiting for service to become stable..."
    
    # Wait for service to be running
    if aws ecs wait services-stable --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION --waiter-config '{"delay": 15, "maxAttempts": 40}'; then
        echo_info "Service is stable"
    else
        echo_warn "Service didn't become stable within timeout, checking current status..."
    fi
    
    # Get service status
    echo_info "Current service status:"
    aws ecs describe-services --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:2]}'
    
    # Get task information
    TASK_ARN=$(aws ecs list-tasks --cluster $APP_NAME-cluster --service-name $APP_NAME-service --query 'taskArns[0]' --output text --region $AWS_REGION)
    
    if [ "$TASK_ARN" != "None" ] && [ "$TASK_ARN" != "" ]; then
        echo_info "Task ARN: $TASK_ARN"
        
        # Get task status
        echo_info "Task status:"
        aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --region $AWS_REGION --query 'tasks[0].{LastStatus:lastStatus,DesiredStatus:desiredStatus,HealthStatus:healthStatus}'
        
        # Get public IP
        ENI_ID=$(aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --region $AWS_REGION --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
        
        if [ "$ENI_ID" != "" ]; then
            PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $AWS_REGION --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
            
            if [ "$PUBLIC_IP" != "None" ] && [ "$PUBLIC_IP" != "" ]; then
                echo_info "=== Deployment Information ==="
                echo_info "Public IP: $PUBLIC_IP"
                echo_info "Application URL: http://$PUBLIC_IP:$CONTAINER_PORT"
                echo_info "Health check: http://$PUBLIC_IP:$CONTAINER_PORT/health"
                echo_info "API Docs: http://$PUBLIC_IP:$CONTAINER_PORT/docs"
                
                # Test connectivity
                echo_info "Testing connectivity..."
                if curl -s --connect-timeout 10 http://$PUBLIC_IP:$CONTAINER_PORT/health &>/dev/null; then
                    echo_info "✓ Application is responding!"
                else
                    echo_warn "Application is not responding yet. Check logs:"
                    echo_info "aws logs tail /ecs/$APP_NAME --follow --region $AWS_REGION"
                fi
            else
                echo_warn "No public IP assigned"
            fi
        else
            echo_warn "No network interface found"
        fi
    else
        echo_warn "No tasks running"
    fi
}

# Main execution
main() {
    echo_info "Starting ECS service fix..."
    
    check_resources
    cleanup_service
    
    if create_service; then
        wait_and_get_info
        echo_info "Service creation completed!"
    else
        echo_error "Failed to create service"
        exit 1
    fi
}

main "$@"
