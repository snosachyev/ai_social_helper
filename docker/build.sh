#!/bin/bash
set -e

echo "Building base images..."

# Build lightweight base
docker build \
  --build-arg HOST_UID=${HOST_UID:-1000} \
  --build-arg HOST_GID=${HOST_GID:-1000} \
  -t rag-base-lightweight:latest \
  -f docker/base/lightweight.Dockerfile .

# Build ML CPU base
docker build \
  --build-arg HOST_UID=${HOST_UID:-1000} \
  --build-arg HOST_GID=${HOST_GID:-1000} \
  -t rag-base-ml-cpu:latest \
  -f docker/base/ml-cpu.Dockerfile .

echo "Essential base images built successfully!"
echo "GPU base image skipped (CUDA runtime not available)"
