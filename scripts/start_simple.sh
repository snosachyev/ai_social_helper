#!/bin/bash

# Simple Start Script for Testing
set -e

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🚀 Starting Simple RAG System for Testing"
echo "========================================="

# Stop existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.yml down || true
$COMPOSE_CMD -f docker-compose.optimized.yml down || true
$COMPOSE_CMD -f docker-compose.simple.yml down || true

# Start simple system
echo "🚀 Starting simple system..."
$COMPOSE_CMD -f docker-compose.simple.yml up -d

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "   Waiting for PostgreSQL..."
timeout 60 bash -c 'until docker exec rag-postgres-simple pg_isready -U rag_user -d rag_db; do sleep 2; done'

# Wait for Redis
echo "   Waiting for Redis..."
timeout 60 bash -c 'until docker exec rag-redis-simple redis-cli ping; do sleep 2; done'

# Wait for API Gateway
echo "   Waiting for API Gateway..."
sleep 30

echo "✅ Simple system is ready!"
echo ""
echo "🌐 Access Points:"
echo "   API Gateway: http://localhost:8000"
echo "   Health: http://localhost:8000/health"
echo ""
echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.simple.yml logs -f"
echo "🧪 Start testing when ready!"
