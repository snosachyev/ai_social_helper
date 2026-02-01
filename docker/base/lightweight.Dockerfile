# Base for lightweight services (auth, api-gateway, document, etc.)
FROM python:3.9-slim

# Install system dependencies once
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install shared Python dependencies
COPY docker/requirements-shared.txt .
RUN pip install --no-cache-dir -r requirements-shared.txt

# Create app user and working directory
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} app \
    && useradd --create-home --shell /bin/bash --uid ${HOST_UID} --gid ${HOST_GID} app

WORKDIR /app
RUN chown -R app:app /app
USER app
