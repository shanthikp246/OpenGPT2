#!/bin/bash

# Debug script for ECS deployment issues
# Run this to diagnose why your application isn't accessible

APP_NAME="squad-gen-app"
AWS_REGION="us-west-2"  # Update if different

echo "=== ECS Service Debugging ==="
echo

# 1. Check service status
echo "1. Checking ECS service status..."
aws ecs describe-services --cluster $APP_NAME-cluster --services $APP_NAME-service --region $AWS_REGION --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:3]}'

echo
echo "2. Checking task status..."
TASK_ARN=$(aws ecs list-tasks --cluster $APP_NAME-cluster --service-name $APP_NAME-service --query 'taskArns[0]' --output text --region $AWS_REGION)

if [ "$TASK_ARN" != "None" ] && [ "$TASK_ARN" != "" ]; then
    aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --region $AWS_REGION --query 'tasks[0].{LastStatus:lastStatus,DesiredStatus:desiredStatus,HealthStatus:healthStatus,StoppedReason:stoppedReason}'
    
    echo
    echo "3. Checking container status..."
    aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --region $AWS_REGION --query 'tasks[0].containers[0].{Name:name,LastStatus:lastStatus,Reason:reason,ExitCode:exitCode}'
    
    echo
    echo "4. Getting recent CloudWatch logs..."
    echo "Fetching last 20 log entries..."
    aws logs get-log-events --log-group-name "/ecs/$APP_NAME" --log-stream-name "ecs/$APP_NAME-container/$(basename $TASK_ARN)" --region $AWS_REGION --query 'events[-20:].message' --output text 2>/dev/null || echo "No logs found or log stream doesn't exist yet"
    
    echo
    echo "5. Checking network configuration..."
    ENI_ID=$(aws ecs describe-tasks --cluster $APP_NAME-cluster --tasks $TASK_ARN --region $AWS_REGION --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
    if [ "$ENI_ID" != "" ]; then
        echo "Network Interface: $ENI_ID"
        PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $AWS_REGION --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
        PRIVATE_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $AWS_REGION --query 'NetworkInterfaces[0].PrivateIpAddress' --output text)
        SG_IDS=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $AWS_REGION --query 'NetworkInterfaces[0].Groups[].GroupId' --output text)
        
        echo "Public IP: $PUBLIC_IP"
        echo "Private IP: $PRIVATE_IP"
        echo "Security Groups: $SG_IDS"
        
        echo
        echo "6. Checking security group rules..."
        for SG_ID in $SG_IDS; do
            echo "Security Group: $SG_ID"
            aws ec2 describe-security-groups --group-ids $SG_ID --region $AWS_REGION --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' --output table
        done
    fi
else
    echo "No running tasks found!"
fi

echo
echo "=== Troubleshooting Steps ==="
echo "1. Check if your FastAPI app is configured to listen on 0.0.0.0:8000 (not 127.0.0.1)"
echo "2. Verify your Dockerfile exposes port 8000"
echo "3. Check CloudWatch logs above for application errors"
echo "4. Ensure your application has a /health endpoint or create one"
echo
echo "=== Quick Fixes ==="
echo "If container keeps restarting, try these commands:"
echo "# Update task definition with health check:"
echo "# Add to your main.py: @app.get('/health') -> return {'status': 'healthy'}"
echo
echo "# Restart service:"
echo "aws ecs update-service --cluster $APP_NAME-cluster --service $APP_NAME-service --force-new-deployment --region $AWS_REGION"
