# Installation Guide

This guide provides step-by-step instructions for setting up the RAG System in different environments.

## 📋 Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 8 cores (16 recommended)
- **Memory**: 32GB RAM (64GB recommended)
- **Storage**: 500GB SSD (1TB recommended)
- **Network**: 1Gbps connection

#### Software Requirements
- **Operating System**: Ubuntu 20.04+ / RHEL 8+ / CentOS 8+ / macOS 10.15+
- **Docker**: 20.10+ with Docker Compose 2.0+
- **Python**: 3.9+ (if running locally)
- **Git**: Latest version

#### Optional (Recommended)
- **GPU**: NVIDIA GPU with 8GB+ VRAM and CUDA 11.0+
- **NVIDIA Container Toolkit**: For GPU support in Docker

## 🚀 Quick Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd ai_social_helper
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

### 3. Start Services
```bash
# Development environment
docker-compose up --build -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Verify Installation
```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## 🔧 Detailed Installation

### Environment Configuration

Create `.env` file with the following variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://rag_user:password@localhost:5432/rag_db
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-this
JWT_SECRET_KEY=your-jwt-secret-key

# Model Configuration
HF_CACHE_DIR=/app/model_cache
MAX_MEMORY_GB=16
ENABLE_GPU=true

# External Services
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Docker Installation

#### Install Docker and Docker Compose
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### GPU Support (Optional)
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Local Development Setup

#### Python Environment
```bash
# Create virtual environment
python3.9 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

#### Database Setup
```bash
# PostgreSQL (Ubuntu)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE USER rag_user WITH PASSWORD 'your_password';
CREATE DATABASE rag_db OWNER rag_user;
GRANT ALL PRIVILEGES ON DATABASE rag_db TO rag_user;
\q

# Redis (Ubuntu)
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

#### Kafka Setup (Optional)
```bash
# Download Kafka
wget https://downloads.apache.org/kafka/3.4.0/kafka_2.13-3.4.0.tgz
tar -xzf kafka_2.13-3.4.0.tgz
cd kafka_2.13-3.4.0

# Start Zookeeper
bin/zookeeper-server-start.sh config/zookeeper.properties &

# Start Kafka
bin/kafka-server-start.sh config/server.properties &
```

## 🌐 Different Installation Modes

### 1. Development Mode
```bash
# Quick start with all services
docker-compose up --build

# With logs
docker-compose up --build --follow-logs

# Specific service
docker-compose up --build api-gateway
```

### 2. Production Mode
```bash
# Production configuration
docker-compose -f docker-compose.prod.yml up -d

# With scaling
docker-compose -f docker-compose.prod.yml up -d --scale api-gateway=3
```

### 3. Kubernetes Mode
```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/secrets/
kubectl apply -f k8s/services/
kubectl apply -f k8s/deployments/

# Check status
kubectl get pods -n rag-system
```

## ✅ Verification Steps

### Health Checks
```bash
# API Gateway
curl http://localhost:8000/health

# Document Service
curl http://localhost:8001/health

# Embedding Service
curl http://localhost:8002/health

# Vector Service
curl http://localhost:8003/health
```

### Service Connectivity
```bash
# Test database connection
docker-compose exec postgres psql -U rag_user -d rag_db -c "SELECT 1;"

# Test Redis connection
docker-compose exec redis redis-cli ping

# Test Kafka connection
docker-compose exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092
```

### API Functionality
```bash
# Upload test document
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@test_document.pdf"

# Query system
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}'
```

## 🔧 Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :8000

# Kill processes
sudo fuser -k 8000/tcp
```

#### Permission Issues
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix file permissions
sudo chown -R $USER:$USER ./data
sudo chmod -R 755 ./data
```

#### Memory Issues
```bash
# Check memory usage
free -h
docker stats

# Increase swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### GPU Issues
```bash
# Check GPU availability
nvidia-smi

# Check NVIDIA Docker
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Log Analysis
```bash
# View service logs
docker-compose logs api-gateway
docker-compose logs document-service

# Real-time logs
docker-compose logs -f embedding-service

# System logs
sudo journalctl -u docker.service
```

## 📊 Performance Optimization

### System Tuning
```bash
# Increase file limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize network
echo "net.core.rmem_max = 134217728" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max = 134217728" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Docker Optimization
```bash
# Clean up unused resources
docker system prune -a

# Optimize build cache
docker builder prune -a

# Monitor resource usage
docker stats --no-stream
```

## 🔄 Updates and Maintenance

### Update Services
```bash
# Pull latest images
docker-compose pull

# Rebuild services
docker-compose up --build --force-recreate

# Update dependencies
pip install --upgrade -r requirements.txt
```

### Backup Configuration
```bash
# Backup environment
cp .env .env.backup.$(date +%Y%m%d)

# Backup data
docker-compose exec postgres pg_dump -U rag_user rag_db > backup.sql
```

## 📚 Next Steps

After successful installation:

1. Read [ARCHITECTURE.md](architecture_design.md) to understand the system
2. Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for production setup
3. Check [API_REFERENCE.md](API_REFERENCE.md) for integration details
4. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review service logs: `docker-compose logs <service>`
3. Consult the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) guide
4. Create an issue with detailed error logs

---

**Version**: 1.0.0  
**Last Updated**: January 2024
