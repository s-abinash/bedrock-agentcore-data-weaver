#!/bin/bash

set -euo pipefail

REPO_URI="683883881884.dkr.ecr.us-west-2.amazonaws.com/data-agent-bedrock-ac"
IMAGE_NAME="${IMAGE_NAME:-pandas-agent-core}"
IMAGE_TAG="${1:-latest}"
# Backward compatible: use PLATFORM if provided, else default to multi-arch
PLATFORMS="${PLATFORMS:-${PLATFORM:-linux/amd64,linux/arm64}}"
REGION="us-west-2"
REPOSITORY_NAME="data-agent-bedrock-ac"
BUILDER_NAME="${BUILDER_NAME:-multiarch-builder}"

echo "Ensuring Docker Buildx builder '${BUILDER_NAME}' exists..."
if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
  docker buildx create --name "${BUILDER_NAME}" --use
else
  docker buildx use "${BUILDER_NAME}"
fi
docker buildx inspect --bootstrap >/dev/null

echo "Authenticating Docker with ECR (${REGION})..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "683883881884.dkr.ecr.${REGION}.amazonaws.com"

echo "Ensuring ECR repository '${REPOSITORY_NAME}' exists..."
aws ecr describe-repositories --repository-names "${REPOSITORY_NAME}" --region "${REGION}" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "${REPOSITORY_NAME}" --region "${REGION}" >/dev/null

echo "Building and pushing with Buildx..."
echo "  Image: ${REPO_URI}:${IMAGE_TAG}"
echo "  Platforms: ${PLATFORMS}"
docker buildx build \
  --platform "${PLATFORMS}" \
  -t "${REPO_URI}:${IMAGE_TAG}" \
  --push \
  .

echo "Successfully pushed image to ${REPO_URI}:${IMAGE_TAG}"
