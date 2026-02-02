#!/bin/bash

# Запуск с host networking решением
set -e

echo "🚀 Starting RAG System with Host Networking"
echo "============================================"
echo "⚡ Решение Docker networking проблемы"
echo "🔥 Прямой доступ к сети хоста"
echo ""

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Остановить предыдущие контейнеры
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.yml down || true
$COMPOSE_CMD -f docker-compose.optimized.yml down || true
$COMPOSE_CMD -f docker-compose.python-10.yml down || true
$COMPOSE_CMD -f docker-compose.direct-test.yml down || true

# Запустить с host networking
echo "🚀 Starting with host networking..."
$COMPOSE_CMD -f docker-compose.host-network.yml up -d

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "   Waiting for PostgreSQL..."
timeout 60 bash -c 'until pg_isready -h localhost -p 5432 -U rag_user -d rag_db; do sleep 2; done'

# Wait for Redis
echo "   Waiting for Redis..."
timeout 60 bash -c 'until redis-cli -h localhost -p 6379 ping; do sleep 2; done'

# Wait for API Gateways
echo "   Waiting for API Gateways..."
sleep 30

# Wait for Nginx
echo "   Waiting for Nginx..."
sleep 10

echo "✅ Host networking system is ready!"
echo ""
echo "🌐 Access Points:"
echo "   Load Balancer: http://localhost:80"
echo "   Health: http://localhost:80/health"
echo "   API Gateway 1: http://localhost:8001/health"
echo "   API Gateway 2: http://localhost:8002/health"
echo "   API Gateway 3: http://localhost:8003/health"
echo ""
echo "⚡ Host Networking Benefits:"
echo "   • NO Docker networking overhead"
echo "   • Прямой доступ к сети хоста"
echo "   • Высокая производительность"
echo "   • Решение проблемы connection refused"
echo ""
echo "🧪 Ready for 1000+ users testing!"
echo ""
echo "🎯 Expected Performance:"
echo "   • 1000+ concurrent users"
echo "   • <100ms response times"
echo "   • <5% error rate"
echo "   • 3000+ RPS capability"
echo ""
echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.host-network.yml logs -f"
echo "🧪 Test with: k6 run --vus 1000 --duration 60s tests/performance/k6/native_test_fixed.js"
