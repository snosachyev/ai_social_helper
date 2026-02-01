# Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the RAG System in a production environment. The deployment covers infrastructure setup, security configuration, monitoring, and operational procedures.

## Development and Testing

### Multi-Stage Docker Build

The system uses multi-stage Docker builds to optimize image sizes and separate testing dependencies from runtime dependencies.

#### Build Stages

1. **Base Stage** - Contains only runtime dependencies
2. **Test Stage** - Contains all dependencies including testing tools
3. **Runtime Stage** - Minimal production image

#### Running Tests

**Unit Tests (Fast, No External Dependencies):**
```bash
docker run --rm $(docker build -q --target test -f services/document-service/Dockerfile .) python -m pytest tests/unit/ -v
```

**Integration Tests (With Infrastructure):**
```bash
# Start required services
docker compose up postgres redis -d

# Run integration tests
docker run --rm --network rag_system_rag-network \
  -e POSTGRES_HOST=postgres \
  -e REDIS_HOST=redis \
  $(docker build -q --target test -f services/document-service/Dockerfile .) \
  python -m pytest tests/integration/ -v
```

**All Tests:**
```bash
# Start infrastructure
docker compose up postgres redis -d

# Run all tests
docker run --rm --network rag_system_rag-network \
  -e POSTGRES_HOST=postgres \
  -e REDIS_HOST=redis \
  $(docker build -q --target test -f services/document-service/Dockerfile .) \
  python -m pytest tests/ -v
```

#### Building Services

**Build Individual Service:**
```bash
docker compose build document-service
```

**Build All Services:**
```bash
docker compose build
```

#### Running Services

**Start Individual Service:**
```bash
docker compose up document-service
```

**Start All Services:**
```bash
docker compose up
```

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU:** 8 cores (16 recommended)
- **Memory:** 32GB RAM (64GB recommended)
- **Storage:** 500GB SSD (1TB recommended)
- **Network:** 1Gbps (10Gbps recommended)
- **GPU:** 8GB VRAM (16GB recommended for large models)

#### Software Requirements
- **Operating System:** Ubuntu 20.04+ / RHEL 8+ / CentOS 8+
- **Docker:** 20.10+ with Docker Compose 2.0+
- **Kubernetes:** 1.24+ (for K8s deployment)
- **NVIDIA Driver:** 470+ (for GPU support)
- **NVIDIA Container Toolkit:** Latest version

### Infrastructure Components

#### Required Services
- **Load Balancer:** HAProxy / NGINX / AWS ALB
- **Database:** PostgreSQL 13+ (managed or self-hosted)
- **Cache:** Redis 6+ (cluster for production)
- **Message Queue:** Apache Kafka 3.0+
- **Storage:** Object storage (S3, MinIO)
- **Monitoring:** Prometheus + Grafana
- **Logging:** ELK Stack or cloud logging

#### Optional Services
- **MLflow:** Model tracking and registry
- **Airflow:** Batch job orchestration
- **ClickHouse:** Analytics database
- **Istio:** Service mesh (for Kubernetes)

## Security Configuration

### 1. SSL/TLS Setup

#### SSL Certificate Configuration
```bash
# Generate SSL certificates (Let's Encrypt recommended)
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### Nginx SSL Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Firewall Configuration

#### UFW Setup
```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow application ports (internal only)
sudo ufw allow from 10.0.0.0/8 to any port 8000:8009
sudo ufw allow from 10.0.0.0/8 to any port 5432
sudo ufw allow from 10.0.0.0/8 to any port 6379
sudo ufw allow from 10.0.0.0/8 to any port 9092
```

### 3. Authentication & Authorization

#### JWT Configuration
```yaml
# config/jwt.yaml
jwt:
  secret_key: ${JWT_SECRET_KEY}
  algorithm: HS256
  access_token_expire_minutes: 30
  refresh_token_expire_days: 7
  issuer: rag-system
  audience: rag-users
```

#### RBAC Setup
```yaml
# config/rbac.yaml
roles:
  admin:
    permissions:
      - documents:read
      - documents:write
      - documents:delete
      - models:manage
      - system:admin
  
  user:
    permissions:
      - documents:read
      - documents:write
      - query:execute
      - generate:execute
  
  readonly:
    permissions:
      - documents:read
      - query:execute
```

## Database Setup

### 1. PostgreSQL Configuration

#### Production PostgreSQL Setup
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Configure PostgreSQL
sudo nano /etc/postgresql/13/main/postgresql.conf
```

```ini
# postgresql.conf
listen_addresses = 'localhost'
port = 5432
max_connections = 200
shared_buffers = 8GB
effective_cache_size = 24GB
maintenance_work_mem = 2GB
checkpoint_completion_target = 0.9
wal_buffers = 64MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

#### Database Security
```bash
# Create database user
sudo -u postgres psql
CREATE USER rag_user WITH PASSWORD 'secure_password';
CREATE DATABASE rag_db OWNER rag_user;
GRANT ALL PRIVILEGES ON DATABASE rag_db TO rag_user;

# Configure pg_hba.conf
sudo nano /etc/postgresql/13/main/pg_hba.conf
```

```
# pg_hba.conf
local   all             postgres                                peer
local   all             rag_user                                md5
host    rag_db          rag_user        127.0.0.1/32           md5
host    rag_db          rag_user        ::1/128                md5
```

### 2. Redis Configuration

#### Production Redis Setup
```bash
# Install Redis
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
```

```ini
# redis.conf
bind 127.0.0.1
port 6379
requirepass your_redis_password
maxmemory 8gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

#### Redis Cluster Setup (Optional)
```bash
# Create Redis cluster
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1
```

### 3. Kafka Configuration

#### Production Kafka Setup
```bash
# Download Kafka
wget https://downloads.apache.org/kafka/3.4.0/kafka_2.13-3.4.0.tgz
tar -xzf kafka_2.13-3.4.0.tgz
cd kafka_2.13-3.4.0
```

```properties
# config/server.properties
broker.id=1
listeners=PLAINTEXT://localhost:9092
advertised.listeners=PLAINTEXT://localhost:9092
zookeeper.connect=localhost:2181
num.network.threads=3
num.io.threads=8
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600
num.partitions=10
num.recovery.threads.per.data.dir=1
offsets.topic.replication.factor=3
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2
log.retention.hours=168
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000
zookeeper.connection.timeout.ms=18000
group.initial.rebalance.delay.ms=0
```

## Application Deployment

### 1. Environment Configuration

#### Production Environment Variables
```bash
# .env.production
NODE_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://rag_user:secure_password@localhost:5432/rag_db
REDIS_URL=redis://:your_redis_password@localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-key

# Model Configuration
HF_CACHE_DIR=/app/model_cache
MAX_MEMORY_GB=16
ENABLE_GPU=true

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
MLFLOW_ENABLED=true

# External Services
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
CLICKHOUSE_URL=clickhouse://default:@localhost:9000/rag_analytics
```

### 2. Docker Compose Production

#### Production Docker Compose
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  api-gateway:
    image: rag-system/api-gateway:latest
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    environment:
      - NODE_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    volumes:
      - ./ssl:/etc/ssl/certs
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  document-service:
    image: rag-system/document-service:latest
    restart: unless-stopped
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 4G
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs

  embedding-service:
    image: rag-system/embedding-service:latest
    restart: unless-stopped
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2.0'
          memory: 8G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ~/.cache/huggingface:/app/hf_cache
      - ./logs:/app/logs

  # ... other services
```

### 3. Kubernetes Deployment

#### Namespace and ConfigMaps
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rag-system

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rag-config
  namespace: rag-system
data:
  NODE_ENV: "production"
  LOG_LEVEL: "INFO"
  DATABASE_URL: "postgresql://rag_user:secure_password@postgres:5432/rag_db"
  REDIS_URL: "redis://:your_redis_password@redis:6379/0"
```

#### Secrets
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-secrets
  namespace: rag-system
type: Opaque
data:
  SECRET_KEY: <base64-encoded-secret>
  JWT_SECRET_KEY: <base64-encoded-jwt-secret>
  DATABASE_PASSWORD: <base64-encoded-db-password>
  REDIS_PASSWORD: <base64-encoded-redis-password>
```

#### Deployment Example
```yaml
# k8s/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: rag-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: rag-system/api-gateway:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: rag-config
        - secretRef:
            name: rag-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Monitoring & Observability

### 1. Prometheus Configuration

#### Prometheus Configuration
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'rag-system'
    static_configs:
      - targets: ['api-gateway:8000', 'document-service:8001']
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

#### Alert Rules
```yaml
# prometheus/alert_rules.yml
groups:
- name: rag-system
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors per second"

  - alert: HighMemoryUsage
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage"
      description: "Memory usage is {{ $value | humanizePercentage }}"
```

### 2. Grafana Dashboards

#### Grafana Configuration
```yaml
# grafana/grafana.ini
[server]
http_port = 3000
root_url = https://grafana.your-domain.com

[database]
type = postgres
host = postgres:5432
name = grafana
user = grafana
password = grafana_password

[security]
admin_user = admin
admin_password = secure_admin_password

[auth.anonymous]
enabled = false
```

#### Dashboard Import
```bash
# Import dashboards
curl -X POST \
  -H "Authorization: Basic $(echo -n admin:secure_admin_password | base64)" \
  -H "Content-Type: application/json" \
  -d @dashboard.json \
  http://localhost:3000/api/dashboards/db
```

### 3. Logging Configuration

#### ELK Stack Setup
```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
      - ./logs:/app/logs
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Performance Optimization

### 1. Database Optimization

#### PostgreSQL Performance Tuning
```sql
-- Create indexes
CREATE INDEX CONCURRENTLY idx_documents_status ON documents(status);
CREATE INDEX CONCURRENTLY idx_documents_created_at ON documents(created_at);
CREATE INDEX CONCURRENTLY idx_embeddings_chunk_id ON embeddings(chunk_id);
CREATE INDEX CONCURRENTLY idx_query_history_created_at ON query_history(created_at);

-- Partition large tables
CREATE TABLE query_history_2024_01 PARTITION OF query_history
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Analyze tables for better query planning
ANALYZE documents;
ANALYZE embeddings;
ANALYZE query_history;
```

#### Connection Pooling
```python
# Connection pool configuration
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30
DATABASE_POOL_TIMEOUT = 30
DATABASE_POOL_RECYCLE = 3600
```

### 2. Caching Strategy

#### Redis Caching Configuration
```python
# Multi-level caching
CACHE_CONFIG = {
    'L1': {
        'type': 'memory',
        'max_size': 1000,
        'ttl': 300  # 5 minutes
    },
    'L2': {
        'type': 'redis',
        'max_size': 10000,
        'ttl': 3600  # 1 hour
    },
    'L3': {
        'type': 'disk',
        'max_size': 100000,
        'ttl': 86400  # 24 hours
    }
}
```

#### Cache Warming Strategy
```python
# Cache warming script
async def warm_cache():
    # Pre-load popular models
    popular_models = [
        "sentence-transformers/all-MiniLM-L6-v2",
        "microsoft/DialoGPT-medium"
    ]
    
    for model_name in popular_models:
        await model_service.load_model(model_name)
    
    # Pre-load recent documents
    recent_docs = await document_service.get_recent_documents(limit=100)
    for doc in recent_docs:
        await cache_service.cache_document(doc)
```

### 3. Model Optimization

#### Model Quantization
```python
# Quantization configuration
QUANTIZATION_CONFIG = {
    'embedding_models': {
        'bitsandbytes': 4,
        'device': 'cuda'
    },
    'generation_models': {
        'bitsandbytes': 8,
        'device': 'cuda'
    }
}
```

#### Batch Processing
```python
# Batch processing configuration
BATCH_CONFIG = {
    'max_batch_size': 32,
    'max_wait_time': 0.1,  # 100ms
    'adaptive_batching': True,
    'priority_levels': 3
}
```

## Backup & Recovery

### 1. Database Backup

#### Automated Backup Script
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="rag_db_backup_$DATE.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
pg_dump -h localhost -U rag_user -d rag_db > "$BACKUP_DIR/$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_DIR/$BACKUP_FILE"

# Remove old backups (keep last 7 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

#### Cron Job for Backups
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh >> /var/log/postgres_backup.log 2>&1
```

### 2. Model Backup

#### Model Cache Backup
```bash
#!/bin/bash
# backup_models.sh

MODEL_CACHE_DIR="/app/model_cache"
BACKUP_DIR="/backups/models"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
rsync -av --delete "$MODEL_CACHE_DIR/" "$BACKUP_DIR/current/"

# Create snapshot
cp -al "$BACKUP_DIR/current" "$BACKUP_DIR/snapshot_$DATE"

# Remove old snapshots (keep last 5)
find "$BACKUP_DIR" -name "snapshot_*" -type d | sort -r | tail -n +6 | xargs rm -rf
```

### 3. Disaster Recovery

#### Recovery Procedures
```bash
# 1. Stop services
docker-compose down

# 2. Restore database
gunzip -c /backups/postgres/rag_db_backup_20240122_020000.sql.gz | psql -h localhost -U rag_user -d rag_db

# 3. Restore model cache
rsync -av /backups/models/current/ /app/model_cache/

# 4. Start services
docker-compose up -d

# 5. Verify health
for service in api-gateway document-service embedding-service; do
  curl -f http://localhost:8000/health
done
```

## Security Hardening

### 1. Container Security

#### Docker Security Configuration
```dockerfile
# Security-hardened Dockerfile
FROM python:3.9-slim as base

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Set security context
USER appuser
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

#### Pod Security Policy
```yaml
# k8s/pod-security-policy.yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: rag-system-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

### 2. Network Security

#### Network Policies
```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: rag-system-netpol
  namespace: rag-system
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
  - to:
    - podSelector:
        matchLabels:
          app: redis
```

### 3. Application Security

#### Security Headers
```python
# Security middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

#### Input Validation
```python
# Input validation
from pydantic import BaseModel, validator

class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    
    @validator('query')
    def validate_query(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Query cannot be empty')
        if len(v) > 1000:
            raise ValueError('Query too long')
        return v.strip()
```

## Scaling Strategies

### 1. Horizontal Scaling

#### Auto-scaling Configuration
```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: rag-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Load Balancer Configuration
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-system-ingress
  namespace: rag-system
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: rag-system-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway-service
            port:
              number: 8000
```

### 2. Vertical Scaling

#### Resource Optimization
```python
# Resource monitoring and optimization
class ResourceOptimizer:
    def __init__(self):
        self.cpu_threshold = 80
        self.memory_threshold = 85
    
    async def optimize_resources(self):
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        
        if cpu_usage > self.cpu_threshold:
            await self.scale_horizontal()
        
        if memory_usage > self.memory_threshold:
            await self.optimize_memory()
```

### 3. Database Scaling

#### Read Replicas
```bash
# Configure read replicas
# In postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 64
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'
```

#### Connection Pooling
```python
# PgBouncer configuration
[databases]
rag_db = host=localhost port=5432 dbname=rag_db

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/pgbouncer/pgbouncer.log
admin_users = postgres
stats_users = stats, postgres
```

## Troubleshooting

### 1. Common Issues

#### Service Not Starting
```bash
# Check logs
docker-compose logs api-gateway

# Check port conflicts
netstat -tulpn | grep :8000

# Check resource usage
docker stats
```

#### Database Connection Issues
```bash
# Test database connection
psql -h localhost -U rag_user -d rag_db -c "SELECT 1;"

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-13-main.log

# Check connection limits
psql -h localhost -U postgres -c "SELECT * FROM pg_stat_activity;"
```

#### Memory Issues
```bash
# Check memory usage
free -h
docker stats --no-stream

# Check GPU memory
nvidia-smi

# Clear model cache
curl -X POST "http://localhost:8006/system/cleanup" \
  -H "Content-Type: application/json" \
  -d '{"days_old": 7}'
```

### 2. Performance Issues

#### Slow Queries
```sql
-- Identify slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Analyze query plan
EXPLAIN ANALYZE SELECT * FROM documents WHERE status = 'completed';
```

#### High Latency
```bash
# Check network latency
ping localhost
traceroute localhost

# Check service latency
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/health"
```

### 3. Monitoring Issues

#### Missing Metrics
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check metric availability
curl http://localhost:8000/metrics | grep http_requests
```

#### Alert Not Firing
```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Test alert manually
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning"}}]'
```

## Maintenance Procedures

### 1. Regular Maintenance

#### Daily Tasks
```bash
#!/bin/bash
# daily_maintenance.sh

# Check service health
for service in api-gateway document-service embedding-service; do
  if ! curl -f http://localhost:8000/health; then
    echo "Service $service is unhealthy"
    # Send alert
  fi
done

# Clean up old logs
find /var/log/rag-system -name "*.log" -mtime +7 -delete

# Check disk space
df -h | grep -E "9[0-9]%" && echo "Disk space critical"
```

#### Weekly Tasks
```bash
#!/bin/bash
# weekly_maintenance.sh

# Update models
curl -X POST "http://localhost:8006/models/update-all"

# Optimize database
psql -h localhost -U rag_user -d rag_db -c "VACUUM ANALYZE;"

# Clean up old data
curl -X POST "http://localhost:8006/system/cleanup" \
  -H "Content-Type: application/json" \
  -d '{"days_old": 30}'
```

### 2. Update Procedures

#### Rolling Update
```bash
# Update one service at a time
docker-compose up -d --no-deps api-gateway
sleep 30
docker-compose up -d --no-deps document-service
sleep 30
docker-compose up -d --no-deps embedding-service
```

#### Blue-Green Deployment
```bash
# Deploy to green environment
docker-compose -f docker-compose.green.yml up -d

# Test green environment
curl http://localhost:8001/health

# Switch traffic
# Update load balancer to point to green

# Remove blue environment
docker-compose -f docker-compose.blue.yml down
```

### 3. Security Updates

#### Security Scanning
```bash
# Scan for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image rag-system/api-gateway:latest

# Update base images
docker pull python:3.9-slim
docker-compose build --no-cache
```

## Conclusion

This production deployment guide provides comprehensive instructions for deploying the RAG System in a production environment. Following these guidelines ensures:

- **High Availability:** Through proper scaling and redundancy
- **Security:** Via comprehensive security measures
- **Performance:** Through optimization and monitoring
- **Reliability:** With proper backup and recovery procedures
- **Maintainability:** With clear operational procedures

Regular maintenance and monitoring are essential for keeping the system running smoothly in production. Always test changes in a staging environment before applying them to production.
