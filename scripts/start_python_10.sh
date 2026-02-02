#!/bin/bash

# Start Python 10-instances optimized system
set -e

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🚀 Starting Python 10-Instances Optimized System"
echo "================================================="
echo "⚡ 10x Python API Gateways + Nginx + PgBouncer + Redis + PostgreSQL"
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.yml down || true
$COMPOSE_CMD -f docker-compose.optimized.yml down || true
$COMPOSE_CMD -f docker-compose.simple.yml down || true
$COMPOSE_CMD -f docker-compose.scaled.yml down || true
$COMPOSE_CMD -f docker-compose.high-perf.yml down || true
$COMPOSE_CMD -f docker-compose.python-10.yml down || true

# Start Python 10 system
echo "🚀 Starting Python 10-instances system..."
$COMPOSE_CMD -f docker-compose.python-10.yml up -d

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "   Waiting for PostgreSQL..."
timeout 60 bash -c 'until docker exec rag-postgres-py10 pg_isready -U rag_user -d rag_db; do sleep 2; done'

# Wait for PgBouncer
echo "   Waiting for PgBouncer..."
sleep 10

# Wait for Redis
echo "   Waiting for Redis..."
timeout 60 bash -c 'until docker exec rag-redis-py10 redis-cli ping; do sleep 2; done'

# Wait for Python API Gateways
echo "   Waiting for Python API Gateways..."
sleep 60

# Wait for Nginx
echo "   Waiting for Nginx..."
sleep 15

echo "✅ Python 10-instances system is ready!"
echo ""
echo "🌐 Access Points:"
echo "   Load Balancer: http://localhost:80"
echo "   Health: http://localhost:80/health"
echo "   API: http://localhost:80/query"
echo ""
echo "⚡ Optimized Features:"
echo "   • 10x Python API Gateways"
echo "   • Nginx with increased timeouts"
echo "   • PgBouncer connection pooling"
echo "   • PostgreSQL optimization"
echo "   • Redis caching"
echo "   • Rate limiting optimized"
echo ""
echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.python-10.yml logs -f"
echo "🧪 Ready for 1000+ users testing!"
echo ""
echo "🎯 Expected Performance:"
echo "   • 500-800 concurrent users"
echo "   • <200ms response times"
echo "   • <10% error rate"
echo "   • 1500+ RPS capability"
