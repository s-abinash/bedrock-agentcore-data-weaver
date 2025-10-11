#!/bin/bash

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh <aws-account-id> [region]"
    echo "Example: ./deploy.sh 123456789012 us-east-1"
    exit 1
fi

ACCOUNT_ID=$1
REGION=${2:-us-east-1}
IMAGE_NAME="pandas-agent-core"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${IMAGE_NAME}"

echo "Building Docker image for ARM64..."
docker build --platform linux/arm64 -t ${IMAGE_NAME}:latest .

echo "Logging into Amazon ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

echo "Creating ECR repository if it doesn't exist..."
aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${REGION} || \
    aws ecr create-repository --repository-name ${IMAGE_NAME} --region ${REGION}

echo "Tagging image..."
docker tag ${IMAGE_NAME}:latest ${ECR_REPO}:latest

echo "Pushing image to ECR..."
docker push ${ECR_REPO}:latest

echo "Successfully deployed ${ECR_REPO}:latest"
echo ""
echo "Next steps:"
echo "1. Go to AWS Bedrock console"
echo "2. Create a new AgentCore"
echo "3. Use the image URI: ${ECR_REPO}:latest"
