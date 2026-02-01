# Base ML Image with shared dependencies
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for ML models
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install shared ML dependencies - these rarely change
COPY docker/requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt

# Install shared application dependencies
COPY docker/requirements-shared.txt .
RUN pip install --no-cache-dir -r requirements-shared.txt

# Create non-root user with host UID/GID for cache access
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} app \
    && useradd --create-home --shell /bin/bash --uid ${HOST_UID} --gid ${HOST_GID} app \
    && chown -R app:app /app

USER app

# Set up cache directories
RUN mkdir -p /app/hf_cache /app/model_cache && chown -R app:app /app/hf_cache /app/model_cache

# Default environment variables
ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_CACHE=/app/hf_cache/hub
ENV HF_CACHE_DIR=/app/hf_cache
ENV HF_OFFLINE_MODE=true
ENV TRANSFORMERS_OFFLINE=1
