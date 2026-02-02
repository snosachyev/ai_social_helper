# 🛠️ Детальный План Оптимизации для 1000+ Пользователей

## 📊 Текущий статус vs Цель

| Метрика | Текущее | Цель | Разрыв |
|---------|---------|------|--------|
| Concurrent Users | 100 | 1000 | 10x |
| Throughput (RPS) | 46 | 500+ | 10x |
| Response Time | 118ms | <300ms | ✅ |
| Success Rate | 100% | >95% | ✅ |

---

## 🎯 **Phase 1: Быстрые улучшения (1-2 дня)**

### 1.1 Оптимизация API Gateway Workers

**Проблема:** Один uvicorn worker = bottleneck
```bash
# Текущий запуск
uvicorn main:app --host 0.0.0.0 --port 8000

# Оптимизированный запуск
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

**Ожидаемый результат:** 4x увеличение throughput

### 1.2 Системные лимиты

**Проблема:** Ограничения на concurrent connections
```bash
# Проверить текущие лимиты
ulimit -n
cat /proc/sys/net/core/somaxconn

# Увеличить лимиты
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
sysctl -w net.core.somaxconn=65536
sysctl -w net.ipv4.tcp_max_syn_backlog=65536
```

**Ожидаемый результат:** Поддержка 1000+ connections

### 1.3 Оптимизация Docker контейнера

**Проблема:** Контейнер с ограниченными ресурсами
```yaml
# docker-compose.optimized.yml
services:
  api-gateway:
    image: rag-api-gateway:optimized
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

---

## 🚀 **Phase 2: Архитектурные улучшения (3-5 дней)**

### 2.1 Horizontal Scaling

**Проблема:** Один экземпляр API Gateway = single point of failure
```yaml
# docker-compose.scale.yml
services:
  api-gateway:
    image: rag-api-gateway:optimized
    deploy:
      replicas: 3
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - api-gateway
```

### 2.2 Load Balancer конфигурация

**Проблема:** Отсутствие распределения нагрузки
```nginx
# nginx.conf
upstream api_gateway {
    least_conn;
    server api-gateway_1:8000 max_fails=3 fail_timeout=30s;
    server api-gateway_2:8000 max_fails=3 fail_timeout=30s;
    server api-gateway_3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://api_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

### 2.3 Connection Pooling

**Проблема:** Каждое запрос создает новое соединение
```python
# Оптимизированный HTTP клиент
import httpx
import asyncio

class OptimizedAPIGateway:
    def __init__(self):
        # Connection pooling для внешних сервисов
        self.client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=1000),
            timeout=httpx.Timeout(30.0)
        )
    
    async def proxy_request(self, service, path, **kwargs):
        # Reuse connections
        return await self.client.request(
            method=kwargs.get('method', 'GET'),
            url=f"{SERVICE_URLS[service]}{path}",
            **kwargs
        )
```

---

## ⚡ **Phase 3: Performance оптимизация (2-3 дня)**

### 3.1 Асинхронная оптимизация

**Проблема:** Блокирующие операции в async коде
```python
# Текущий код (проблемный)
async def upload_document(request: Request):
    data = await request.json()
    await asyncio.sleep(0.1)  # Блокирующая задержка
    return {"success": True}

# Оптимизированный код
async def upload_document(request: Request):
    data = await request.json()
    # Убрать искусственные задержки
    # Добавить real processing
    return await process_document_async(data)
```

### 3.2 Middleware оптимизация

**Проблема:** Тяжелый middleware для каждого запроса
```python
# Оптимизированный middleware
@app.middleware("http")
async def optimized_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Skip rate limiting для load testing
    if request.headers.get("X-Load-Test") == "true":
        response = await call_next(request)
    else:
        # Быстрый rate limiting
        if not rate_limiter.is_allowed_fast(request.client.host):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"}
            )
        response = await call_next(request)
    
    # Минимальные метрики
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    return response
```

### 3.3 Memory оптимизация

**Проблема:** Memory leaks при высокой нагрузке
```python
# Оптимизированная работа с памятью
class MemoryOptimizedGateway:
    def __init__(self):
        # Object pooling для частых объектов
        self.response_pool = []
        self.request_pool = []
    
    async def handle_request(self, request):
        # Reuse объекты вместо создания новых
        response = self.get_response_from_pool()
        try:
            await self.process_request(request, response)
            return response
        finally:
            self.return_response_to_pool(response)
```

---

## 🗄️ **Phase 4: Database & External Services (2-3 дня)**

### 4.1 Database Connection Pooling

**Проблема:** Отсутствие connection pooling
```python
# Оптимизированная работа с базой данных
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine

class DatabaseManager:
    def __init__(self):
        self.engine = create_async_engine(
            "postgresql+asyncpg://user:pass@localhost/db",
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )
    
    async def get_documents(self):
        async with self.engine.begin() as conn:
            result = await conn.execute("SELECT * FROM documents LIMIT 100")
            return result.fetchall()
```

### 4.2 Redis кэширование

**Проблема**: Отсутствие кэширования частых запросов
```python
# Оптимизированное кэширование
import redis.asyncio as redis

class CacheManager:
    def __init__(self):
        self.redis = redis.Redis(host='redis', port=6379)
    
    async def get_cached_documents(self):
        cached = await self.redis.get("documents:list")
        if cached:
            return json.loads(cached)
        
        # Если нет в кэше
        documents = await self.fetch_from_database()
        await self.redis.setex("documents:list", 300, json.dumps(documents))
        return documents
```

---

## 📊 **Phase 5: Monitoring & Observability (1-2 дня)**

### 5.1 Prometheus метрики

**Проблема**: Отсутствие детального мониторинга
```python
# Добавить метрики
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter('http_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ACTIVE_CONNECTIONS.inc()
    start_time = time.time()
    
    try:
        response = await call_next(request)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        return response
    finally:
        REQUEST_DURATION.observe(time.time() - start_time)
        ACTIVE_CONNECTIONS.dec()
```

### 5.2 Health checks оптимизация

**Проблема**: Heavy health checks
```python
# Быстрые health checks
@app.get("/health")
async def health_check():
    # Проверить только критические сервисы
    checks = {
        "database": await check_database_connection(),
        "redis": await check_redis_connection(),
        "memory": check_memory_usage()
    }
    
    all_healthy = all(checks.values())
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "timestamp": time.time()
    }
```

---

## 🧪 **Phase 6: Load Testing оптимизация (1 день)**

### 6.1 k6 установка и настройка

**Проблема**: Locust не справляется с 1000+ users
```bash
# Установка k6
curl https://dl.k6.io/deb/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### 6.2 k6 скрипт для 1000 пользователей

```javascript
// k6_load_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 500 },  // Ramp up to 500 users
    { duration: '10m', target: 1000 }, // Ramp up to 1000 users
    { duration: '5m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<300'], // 95% under 300ms
    http_req_failed: ['rate<0.05'],    // Less than 5% errors
  },
};

export default function() {
  let token = `test-load-token-${Math.floor(Math.random() * 100) + 1}`;
  let headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Load-Test': 'true'
  };
  
  // Test different endpoints
  let responses = [
    http.get('http://localhost/health', { headers }),
    http.get('http://localhost/documents', { headers }),
    http.post('http://localhost/query', JSON.stringify({
      query: 'test query',
      top_k: 5
    }), { headers })
  ];
  
  check(responses[0], {
    'health status is 200': (r) => r.status === 200,
  });
  
  sleep(1);
}
```

---

## 📈 **Ожидаемые результаты по фазам:**

| Phase | Concurrent Users | Throughput (RPS) | Success Rate |
|-------|------------------|-----------------|--------------|
| Текущий | 100 | 46 | 100% |
| Phase 1 | 200-300 | 150-200 | 95-98% |
| Phase 2 | 400-600 | 300-400 | 95-98% |
| Phase 3 | 600-800 | 400-500 | 95-98% |
| Phase 4+ | 1000+ | 500+ | 95%+ |

---

## 🎯 **Приоритеты и timeline:**

### 🔥 **Critical (сделать сейчас):**
1. **Увеличить workers** - 4x улучшение за 1 час
2. **Системные лимиты** - поддержка 1000+ connections
3. **k6 для тестирования** - реальная нагрузка

### ⚡ **High Priority (неделя):**
1. **Horizontal scaling** - 3x экземпляра
2. **Load balancer** - распределение нагрузки
3. **Connection pooling** - оптимизация сети

### 📊 **Medium Priority (2 недели):**
1. **Database optimization** - connection pooling
2. **Caching layer** - Redis
3. **Monitoring** - Prometheus + Grafana

---

## 🛠️ **Конкретные команды для оптимизации:**

```bash
# Phase 1 - Быстрый старт
# 1. Оптимизировать API Gateway
docker stop ai_social_helper-test-api-gateway-1
docker run -d --name api-gateway-optimized \
  --network ai_social_helper_test-network \
  -p 8000:8000 \
  --ulimit nofile=65536 \
  rag-api-gateway:simple \
  uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000

# 2. Увеличить системные лимиты
ulimit -n 65536
sysctl -w net.core.somaxconn=65536

# 3. Тест с k6
k6 run --vus 500 --duration 120s k6_load_test.js
```

**🎯 Через 1-2 недели система будет готова к 1000+ concurrent пользователей с >95% success rate!**
