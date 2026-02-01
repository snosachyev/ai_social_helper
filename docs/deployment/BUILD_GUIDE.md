# Build Guide

This guide covers building and compiling the RAG System components for different environments.

## 🔧 Build Overview

The RAG System uses a multi-stage Docker build process optimized for production deployment. Each microservice is built independently with proper dependency management and layer caching.

## 📋 Prerequisites

### Build Tools Required
- **Docker**: 20.10+ with BuildKit enabled
- **Docker Compose**: 2.0+
- **Python**: 3.9+ (for local builds)
- **Git**: Latest version
- **Make**: Optional, for convenience scripts

### Enable Docker BuildKit
```bash
# Enable BuildKit for better performance
export DOCKER_BUILDKIT=1

# Or enable permanently
echo '{"features":{"buildkit":true}}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

## 🏗️ Build Architecture

### Multi-Stage Build Process
```
Stage 1: Base Python Image
Stage 2: Dependencies Installation
Stage 3: Application Code
Stage 4: Production Runtime
```

### Build Optimization
- **Layer Caching**: Optimized Dockerfile layer ordering
- **Parallel Builds**: Multiple services built simultaneously
- **Dependency Caching**: Pip cache mounted during builds
- **Size Optimization**: Minimal production images

## 🚀 Quick Build

### All Services
```bash
# Build all services
docker-compose build

# Build with no cache
docker-compose build --no-cache

# Build specific service
docker-compose build api-gateway

# Parallel build
docker-compose build --parallel
```

### Production Build
```bash
# Production configuration
docker-compose -f docker-compose.prod.yml build

# Optimized production build
docker-compose -f docker-compose.prod.yml build --parallel
```

## 📁 Service Build Details

### API Gateway
```bash
# Build individually
cd services/api-gateway
docker build -t rag-system/api-gateway:latest .

# With build args
docker build \
  --build-arg BUILD_ENV=production \
  --build-arg VERSION=1.0.0 \
  -t rag-system/api-gateway:1.0.0 .
```

### Document Service
```bash
cd services/document-service
docker build -t rag-system/document-service:latest .

# With GPU support
docker build \
  --build-arg ENABLE_GPU=true \
  -t rag-system/document-service:gpu .
```

### Embedding Service (GPU Optimized)
```bash
cd services/embedding-service
docker build -f Dockerfile.gpu -t rag-system/embedding-service:gpu .

# CPU-only version
docker build -f Dockerfile.cpu -t rag-system/embedding-service:cpu .
```

## 🔨 Local Development Build

### Python Environment
```bash
# Setup virtual environment
python3.9 -m venv .venv
source .venv/bin/activate

# Install build dependencies
pip install -r requirements-build.txt

# Install package in development mode
pip install -e ./services/api-gateway
pip install -e ./services/document-service
pip install -e ./services/embedding-service
```

### Build from Source
```bash
# Build all services locally
make build-all

# Individual service build
make build-service SERVICE=api-gateway

# Clean build
make clean-build
```

## 🏭 Production Build Pipeline

### CI/CD Build Script
```bash
#!/bin/bash
# build-production.sh

set -e

VERSION=${1:-latest}
REGISTRY=${2:-docker.io/your-org}

echo "Building RAG System v$VERSION for production..."

# Build all services
services=("api-gateway" "document-service" "embedding-service" "vector-service" "retrieval-service" "generation-service")

for service in "${services[@]}"; do
    echo "Building $service..."
    docker build \
        --build-arg VERSION=$VERSION \
        --build-arg BUILD_ENV=production \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        -t $REGISTRY/$service:$VERSION \
        -t $REGISTRY/$service:latest \
        ./services/$service/
done

echo "Build completed successfully!"
```

### Multi-Platform Build
```bash
# Build for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag rag-system/api-gateway:multiarch \
  ./services/api-gateway/

# Push to registry
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag rag-system/api-gateway:latest \
  --push \
  ./services/api-gateway/
```

## ⚡ Build Optimization

### Dockerfile Optimization
```dockerfile
# Optimized Dockerfile example
FROM python:3.9-slim as base

# Set build arguments
ARG BUILD_ENV=development
ARG VERSION=latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment
ENV BUILD_ENV=${BUILD_ENV}
ENV VERSION=${VERSION}
ENV PYTHONPATH=/app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Caching Strategy
```bash
# Use build cache efficiently
docker build \
  --cache-from rag-system/api-gateway:latest \
  --cache-to type=inline \
  -t rag-system/api-gateway:latest \
  ./services/api-gateway/

# Parallel builds with cache
docker-compose build --parallel --pull
```

## 🧪 Testing Builds

### Build Validation
```bash
# Test built images
docker run --rm rag-system/api-gateway:latest python -c "import fastapi; print('OK')"

# Health check test
docker run --rm -p 8001:8000 rag-system/api-gateway:latest &
sleep 5
curl http://localhost:8001/health
```

### Integration Testing
```bash
# Build and test
docker-compose -f docker-compose.test.yml build
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Test specific service
docker-compose -f docker-compose.test.yml up api-gateway-test
```

## 📦 Build Artifacts

### Image Tagging Strategy
```bash
# Semantic versioning
docker build -t rag-system/api-gateway:1.0.0 .
docker build -t rag-system/api-gateway:1.0 .
docker build -t rag-system/api-gateway:latest .

# Environment-specific
docker build -t rag-system/api-gateway:dev .
docker build -t rag-system/api-gateway:staging .
docker build -t rag-system/api-gateway:prod .

# Git-based tagging
docker build -t rag-system/api-gateway:$(git rev-parse --short HEAD) .
docker build -t rag-system/api-gateway:$(git branch --show-current) .
```

### Registry Management
```bash
# Push to registry
docker push rag-system/api-gateway:latest
docker push rag-system/api-gateway:1.0.0

# Pull from registry
docker pull rag-system/api-gateway:latest

# List available tags
docker image ls rag-system/api-gateway
```

## 🔧 Custom Builds

### GPU-Enabled Builds
```bash
# Build with CUDA support
docker build \
  --build-arg CUDA_VERSION=11.8 \
  --build-arg PYTORCH_VERSION=2.0.0 \
  -f Dockerfile.gpu \
  -t rag-system/embedding-service:gpu \
  ./services/embedding-service/
```

### Minimal Builds
```bash
# Build minimal runtime image
docker build \
  --build-arg INSTALL_DEV=false \
  --build-arg INSTALL_DOCS=false \
  -f Dockerfile.minimal \
  -t rag-system/api-gateway:minimal \
  ./services/api-gateway/
```

### Debug Builds
```bash
# Build with debugging tools
docker build \
  --build-arg INSTALL_DEBUG=true \
  -f Dockerfile.debug \
  -t rag-system/api-gateway:debug \
  ./services/api-gateway/
```

## 🚨 Build Troubleshooting

### Common Issues

#### Memory Issues
```bash
# Increase Docker memory limit
# In Docker Desktop: Preferences > Resources > Memory

# Build with limited memory
docker build --memory=4g ./services/api-gateway/
```

#### Network Issues
```bash
# Use faster package mirrors
docker build \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple/ \
  ./services/api-gateway/

# Use build cache offline
docker build --cache-from type=registry,ref=rag-system/api-gateway:cache .
```

#### Permission Issues
```bash
# Fix Docker socket permissions
sudo chmod 666 /var/run/docker.sock

# Or add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Debug Builds
```bash
# Verbose build output
docker build --progress=plain ./services/api-gateway/

# Interactive debugging
docker run -it --rm rag-system/api-gateway:latest /bin/bash

# Build with shell access
docker run -it --rm --entrypoint /bin/bash rag-system/api-gateway:latest
```

## 📊 Build Performance

### Build Time Optimization
```bash
# Parallel builds
docker-compose build --parallel

# Use BuildKit
DOCKER_BUILDKIT=1 docker-compose build

# Cache optimization
docker builder prune --keep-storage 10GB
```

### Size Optimization
```bash
# Analyze image size
docker history rag-system/api-gateway:latest
docker scan rag-system/api-gateway:latest

# Multi-stage builds reduce final image size
# See Dockerfile examples above
```

## 🔄 Build Automation

### Makefile
```makefile
# Makefile
.PHONY: build build-all build-service clean-build

build-all:
	docker-compose build --parallel

build-service:
	docker-compose build $(SERVICE)

clean-build:
	docker-compose down
	docker system prune -f
	docker-compose build --no-cache

build-prod:
	docker-compose -f docker-compose.prod.yml build --parallel

push-images:
	docker-compose -f docker-compose.prod.yml push
```

### GitHub Actions
```yaml
# .github/workflows/build.yml
name: Build and Push

on:
  push:
    branches: [main, develop]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
        
      - name: Login to Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ secrets.REGISTRY }}
          username: ${{ secrets.USERNAME }}
          password: ${{ secrets.PASSWORD }}
          
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ secrets.REGISTRY }}/rag-system:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## 📚 Next Steps

After successful builds:

1. Test images with `docker-compose up`
2. Deploy to staging environment
3. Run integration tests
4. Deploy to production
5. Monitor build performance

For deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

---

**Version**: 1.0.0  
**Last Updated**: January 2024
