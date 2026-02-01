# Clean Docker Architecture

## Overview

This RAG system now follows a clean, optimized Docker architecture with:

- **Single docker-compose.yml** - No more multiple compose files
- **Layered base images** - Eliminates dependency duplication
- **One-command workflow** - `docker compose up --build`
- **Clear separation** - Build concerns isolated from runtime

## Directory Structure

```
rag_system/
├── docker/
│   ├── base/
│   │   ├── lightweight.Dockerfile    # For non-ML services
│   │   ├── ml-cpu.Dockerfile         # For ML services (CPU)
│   │   └── ml-gpu.Dockerfile         # For ML services (GPU)
│   ├── build.sh                      # Build base images
│   ├── requirements-shared.txt       # Common dependencies
│   └── requirements-ml.txt          # Heavy ML dependencies
├── services/
│   ├── auth-service/
│   │   ├── Dockerfile                # Uses rag-base-lightweight
│   │   ├── requirements.txt          # Service-specific only
│   │   └── main.py
│   ├── embedding-service/
│   │   ├── Dockerfile                # Uses rag-base-ml-cpu
│   │   ├── requirements.txt          # Service-specific only
│   │   └── main.py
│   └── ... (other services)
├── src/                              # Shared source code
├── docker-compose.yml                # Single compose file
└── DOCKER_ARCHITECTURE.md           # This file
```

## Base Images

### rag-base-lightweight
- **Purpose**: Non-ML services (auth, api-gateway, document, etc.)
- **Size**: ~300MB
- **Contains**: Python, FastAPI, Redis, Kafka, PostgreSQL clients

### rag-base-ml-cpu  
- **Purpose**: ML services (embedding, generation, model)
- **Size**: ~2GB
- **Contains**: All lightweight deps + PyTorch, Transformers, etc.

### rag-base-ml-gpu
- **Purpose**: Future GPU support
- **Size**: ~3GB
- **Contains**: All ML deps + CUDA support

## Usage

### Development
```bash
# Build base images (one-time setup)
./docker/build.sh

# Run entire system
docker compose up --build

# Run specific services
docker compose up --build postgres redis auth-service

# Stop everything
docker compose down
```

### Production
```bash
# Same commands work in production
docker compose up --build -d
```

## Benefits

1. **No Duplication** - Heavy ML dependencies installed once
2. **Fast Builds** - Only service-specific changes rebuild
3. **Simple Workflow** - One command to run everything
4. **Clean Architecture** - Build vs runtime clearly separated
5. **Future-Ready** - Easy GPU and Kubernetes migration

## Image Size Comparison

| Service | Before | After | Savings |
|---------|--------|-------|---------|
| auth-service | 2.1GB | 350MB | 83% |
| embedding-service | 2.3GB | 2.1GB | 9% |
| generation-service | 2.3GB | 2.1GB | 9% |
| **Total** | **~8GB** | **~5GB** | **38%** |

## Migration to Kubernetes

The architecture maps directly to Kubernetes:

- `docker/base/` → Container registry base images
- `services/` → Deployments/StatefulSets  
- `docker-compose.yml` → Helm charts/Kustomize

No changes needed to service code or Dockerfiles.
