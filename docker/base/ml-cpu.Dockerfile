# Base for ML services (CPU inference)
FROM python:3.9-slim

# Install ML system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install ML stack once
COPY docker/requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt

# Install shared dependencies
COPY docker/requirements-shared.txt .
RUN pip install --no-cache-dir -r requirements-shared.txt

# Create app user and working directory
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} app \
    && useradd --create-home --shell /bin/bash --uid ${HOST_UID} --gid ${HOST_GID} app

WORKDIR /app
RUN chown -R app:app /app \
    && mkdir -p /app/hf_cache /app/model_cache \
    && chown -R app:app /app/hf_cache /app/model_cache
USER app

ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_CACHE=/app/hf_cache/hub
ENV HF_CACHE_DIR=/app/hf_cache
ENV HF_OFFLINE_MODE=true
ENV TRANSFORMERS_OFFLINE=1
