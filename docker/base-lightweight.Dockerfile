# Base Image for lightweight services (no ML dependencies)
FROM python:3.9-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install shared application dependencies
COPY docker/requirements-shared.txt .
RUN pip install --no-cache-dir -r requirements-shared.txt

# Create non-root user
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} app \
    && useradd --create-home --shell /bin/bash --uid ${HOST_UID} --gid ${HOST_GID} app \
    && chown -R app:app /app

USER app
