# Base for ML services (GPU inference) - future-ready
FROM nvidia/cuda:11.8-devel-ubuntu20.04

# Install Python and ML system dependencies
RUN apt-get update && apt-get install -y \
    python3.9 \
    python3.9-pip \
    python3.9-dev \
    python3.9-venv \
    curl \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.9 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install ML stack with CUDA support
COPY docker/requirements-ml-gpu.txt .
RUN pip install --no-cache-dir -r requirements-ml-gpu.txt

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
ENV CUDA_VISIBLE_DEVICES=0
