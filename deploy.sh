#!/bin/bash

set -euo pipefail

REPO_URI="683883881884.dkr.ecr.us-west-2.amazonaws.com/data-agent-bedrock-ac"
IMAGE_NAME="${IMAGE_NAME:-pandas-agent-core}"
IMAGE_TAG="${1:-latest}"
PLATFORM="${PLATFORM:-linux/arm64}"
REGION="us-west-2"
REPOSITORY_NAME="data-agent-bedrock-ac"

echo "Building Docker image (${IMAGE_NAME}:${IMAGE_TAG}) for platform ${PLATFORM}..."
docker build --platform "${PLATFORM}" -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "Authenticating Docker with ECR (${REGION})..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "683883881884.dkr.ecr.${REGION}.amazonaws.com"

echo "Ensuring ECR repository '${REPOSITORY_NAME}' exists..."
aws ecr describe-repositories --repository-names "${REPOSITORY_NAME}" --region "${REGION}" >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name "${REPOSITORY_NAME}" --region "${REGION}"

echo "Tagging image for push..."
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"

echo "Pushing image to ${REPO_URI}:${IMAGE_TAG}..."
docker push "${REPO_URI}:${IMAGE_TAG}"

echo "Successfully pushed image to ${REPO_URI}:${IMAGE_TAG}"
