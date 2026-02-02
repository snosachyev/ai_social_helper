#!/bin/bash

# High-Performance System Startup Script for 1000+ Users
set -e

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "🚀 Starting Optimized RAG System for 1000+ Users"
echo "================================================"

# Check system requirements
check_requirements() {
    echo "📋 Checking system requirements..."
    
    # Check available memory
    TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_MEM" -lt 16 ]; then
        echo "⚠️  Warning: System has less than 16GB RAM. Performance may be limited."
    else
        echo "✅ Memory: ${TOTAL_MEM}GB available"
    fi
    
    # Check CPU cores
    CPU_CORES=$(nproc)
    if [ "$CPU_CORES" -lt 8 ]; then
        echo "⚠️  Warning: System has less than 8 CPU cores. Performance may be limited."
    else
        echo "✅ CPU: ${CPU_CORES} cores available"
    fi
    
    # Check Docker
if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose (new version)
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose is not installed"
        exit 1
    fi
    
    # Set compose command
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    echo "✅ Docker and Docker Compose available: $COMPOSE_CMD"
    
    echo "✅ System requirements check completed"
}

# Optimize system settings
optimize_system() {
    echo "🔧 Optimizing system settings..."
    
    # Increase file descriptor limits
    if [ "$EUID" -eq 0 ]; then
        echo "Setting system limits..."
        sysctl -w net.core.somaxconn=65535
        sysctl -w net.ipv4.tcp_max_syn_backlog=65535
        sysctl -w net.core.netdev_max_backlog=5000
        sysctl -w vm.swappiness=10
        echo "✅ System limits optimized"
    else
        echo "⚠️  Running without root privileges. Some optimizations skipped."
        echo "   Consider running with sudo for full optimization:"
        echo "   sudo $0"
    fi
    
    # Set user limits
    ulimit -n 65535
    ulimit -u 32768
    echo "✅ User limits set"
}

# Create necessary directories
create_directories() {
    echo "📁 Creating necessary directories..."
    
    mkdir -p infrastructure/postgres
    mkdir -p infrastructure/redis
    mkdir -p infrastructure/nginx
    mkdir -p uploads
    mkdir -p model_cache
    mkdir -p logs
    
    echo "✅ Directories created"
}

# Stop existing containers
stop_existing() {
    echo "🛑 Stopping existing containers..."
    
    $COMPOSE_CMD -f docker-compose.yml down || true
    $COMPOSE_CMD -f docker-compose.optimized.yml down || true
    
    # Wait for containers to stop
    sleep 5
    
    echo "✅ Existing containers stopped"
}

# Start optimized system
start_optimized() {
    echo "🚀 Starting optimized system..."
    
    # Start with optimized compose file
    $COMPOSE_CMD -f docker-compose.optimized.yml up -d
    
    echo "✅ Containers starting..."
    
    # Wait for services to be ready
    echo "⏳ Waiting for services to be ready..."
    
    # Wait for PostgreSQL
    echo "   Waiting for PostgreSQL..."
    timeout 60 bash -c 'until docker exec rag-postgres-optimized pg_isready -U rag_user -d rag_db; do sleep 2; done'
    
    # Wait for Redis
    echo "   Waiting for Redis..."
    timeout 60 bash -c 'until docker exec rag-redis-optimized redis-cli ping; do sleep 2; done'
    
    # Wait for API Gateway instances
    echo "   Waiting for API Gateways..."
    sleep 30
    
    echo "✅ All services are ready!"
}

# Verify system health
verify_health() {
    echo "🏥 Verifying system health..."
    
    # Check if services are responding
    echo "   Testing API Gateway..."
    if curl -f http://localhost/health > /dev/null 2>&1; then
        echo "   ✅ API Gateway healthy"
    else
        echo "   ❌ API Gateway not responding"
        return 1
    fi
    
    echo "   Testing individual services..."
    
    # Test PostgreSQL
    if docker exec rag-postgres-optimized pg_isready -U rag_user -d rag_db > /dev/null 2>&1; then
        echo "   ✅ PostgreSQL healthy"
    else
        echo "   ❌ PostgreSQL not responding"
    fi
    
    # Test Redis
    if docker exec rag-redis-optimized redis-cli ping > /dev/null 2>&1; then
        echo "   ✅ Redis healthy"
    else
        echo "   ❌ Redis not responding"
    fi
    
    echo "✅ Health check completed"
}

# Show system status
show_status() {
    echo "📊 System Status:"
    echo "=================="
    
    $COMPOSE_CMD -f docker-compose.optimized.yml ps
    
    echo ""
    echo "🌐 Access Points:"
    echo "   Main API: http://localhost"
    echo "   Health: http://localhost/health"
    echo "   Metrics: http://localhost/metrics"
    echo ""
    echo "📈 Monitoring:"
    echo "   Grafana: http://localhost:3000 (admin/admin)"
    echo "   Prometheus: http://localhost:9090"
    echo ""
    echo "🧪 Load Testing:"
    echo "   k6 run tests/performance/k6/load_test_1000.js"
    echo "   k6 run tests/performance/k6/stress_test.js"
}

# Main execution
main() {
    echo "Starting optimized system deployment..."
    echo ""
    
    check_requirements
    echo ""
    
    optimize_system
    echo ""
    
    create_directories
    echo ""
    
    stop_existing
    echo ""
    
    start_optimized
    echo ""
    
    sleep 10
    verify_health
    echo ""
    
    show_status
    
    echo ""
    echo "🎉 Optimized system is ready for 1000+ users!"
    echo "📝 Check logs with: $COMPOSE_CMD -f docker-compose.optimized.yml logs -f"
    echo "🧪 Start load testing when ready!"
}

# Handle script interruption
trap 'echo "🛑 Script interrupted. Cleaning up..."; $COMPOSE_CMD -f docker-compose.optimized.yml down; exit 1' INT

# Run main function
main "$@"
