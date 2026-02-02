#!/bin/bash

# Scaled Start Script for 1000+ Users Testing
set -e

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🚀 Starting Scaled RAG System for 1000+ Users"
echo "============================================"

# Stop existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.yml down || true
$COMPOSE_CMD -f docker-compose.optimized.yml down || true
$COMPOSE_CMD -f docker-compose.simple.yml down || true
$COMPOSE_CMD -f docker-compose.scaled.yml down || true

# Start scaled system
echo "🚀 Starting scaled system with Nginx load balancer..."
$COMPOSE_CMD -f docker-compose.scaled.yml up -d

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "   Waiting for PostgreSQL..."
timeout 60 bash -c 'until docker exec rag-postgres-scaled pg_isready -U rag_user -d rag_db; do sleep 2; done'

# Wait for Redis
echo "   Waiting for Redis..."
timeout 60 bash -c 'until docker exec rag-redis-scaled redis-cli ping; do sleep 2; done'

# Wait for API Gateways
echo "   Waiting for API Gateways..."
sleep 30

# Wait for Nginx
echo "   Waiting for Nginx..."
sleep 10

echo "✅ Scaled system is ready!"
echo ""
echo "🌐 Access Points:"
echo "   Load Balancer: http://localhost:80"
echo "   Health: http://localhost:80/health"
echo "   API: http://localhost:80/query"
echo ""
echo "🔧 Internal Services:"
echo "   API Gateway 1: http://localhost:8001 (direct)"
echo "   API Gateway 2: http://localhost:8002 (direct)"
echo "   API Gateway 3: http://localhost:8003 (direct)"
echo ""
echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.scaled.yml logs -f"
echo "🧪 Ready for 1000+ users testing!"
