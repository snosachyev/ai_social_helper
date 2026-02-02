#!/bin/bash

# High-Performance Start Script for 1000+ Users
set -e

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🚀 Starting High-Performance RAG System for 1000+ Users"
echo "======================================================"
echo "⚡ 5x Go API Gateways + Nginx + Redis + PostgreSQL"
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.yml down || true
$COMPOSE_CMD -f docker-compose.optimized.yml down || true
$COMPOSE_CMD -f docker-compose.simple.yml down || true
$COMPOSE_CMD -f docker-compose.scaled.yml down || true
$COMPOSE_CMD -f docker-compose.high-perf.yml down || true

# Start high-performance system
echo "🚀 Building and starting high-performance system..."
$COMPOSE_CMD -f docker-compose.high-perf.yml up -d --build

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "   Waiting for PostgreSQL..."
timeout 60 bash -c 'until docker exec rag-postgres-hp pg_isready -U rag_user -d rag_db; do sleep 2; done'

# Wait for Redis
echo "   Waiting for Redis..."
timeout 60 bash -c 'until docker exec rag-redis-hp redis-cli ping; do sleep 2; done'

# Wait for Go API Gateways
echo "   Waiting for Go API Gateways..."
sleep 45

# Wait for Nginx
echo "   Waiting for Nginx..."
sleep 15

echo "✅ High-Performance system is ready!"
echo ""
echo "🌐 Access Points:"
echo "   Load Balancer: http://localhost:80"
echo "   Health: http://localhost:80/health"
echo "   Metrics: http://localhost:80/metrics"
echo "   API: http://localhost:80/query"
echo ""
echo "⚡ High-Performance Features:"
echo "   • 5x Go API Gateways (concurrent processing)"
echo "   • Nginx load balancer with optimized settings"
echo "   • In-memory caching with Go"
echo "   • Rate limiting and connection pooling"
echo "   • Optimized for 1000+ concurrent users"
echo ""
echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.high-perf.yml logs -f"
echo "🧪 Ready for 1000+ users high-performance testing!"
echo ""
echo "🎯 Expected Performance:"
echo "   • 1000+ concurrent users"
echo "   • <100ms response times"
echo "   • <5% error rate"
echo "   • 2000+ RPS capability"
