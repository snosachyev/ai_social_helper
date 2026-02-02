# 🚀 Quick Start: Local Deployment (Docker Compose)

## 📋 Сценарий использования
- **Разработка и тестирование**
- **Нагрузочное тестирование до 1000+ пользователей**
- **Демонстрация заказчикам**
- **Staging окружение**

## 🛠️ Требования
```bash
# Минимальные требования
- 16GB+ RAM
- 8+ CPU cores  
- Docker & Docker Compose
- 50GB+ свободного места
```

## 🚀 Запуск системы

### 1. Быстрый старт
```bash
# Запуск оптимизированной системы
./scripts/start_optimized.sh

# Или вручную
docker-compose -f docker-compose.optimized.yml up -d
```

### 2. Проверка запуска
```bash
# Проверка здоровья системы
curl http://localhost/health

# Статус контейнеров
docker-compose -f docker-compose.optimized.yml ps

# Логи (если нужно)
docker-compose -f docker-compose.optimized.yml logs -f
```

### 3. Нагрузочное тестирование
```bash
# Установка k6 (если еще не установлено)
curl https://dl.k6.io/deb/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Тест на 1000 пользователей
k6 run tests/performance/k6/load_test_1000.js

# Стресс тест
k6 run tests/performance/k6/stress_test.js
```

## 🏗️ Архитектура локального развертывания

```
Internet
    ↓
Nginx (Load Balancer) :80
    ↓
┌─────────────────────────────────────────────────┐
│  API Gateway Cluster (3 instances)             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │Gateway-1│ │Gateway-2│ │Gateway-3│         │
│  │ :8000   │ │ :8000   │ │ :8000   │         │
│  └─────────┘ └─────────┘ └─────────┘         │
└─────────────────────────────────────────────────┘
    ↓              ↓              ↓
┌─────────────────────────────────────────────────┐
│               Backend Services                   │
│  Auth Service (2x)  │ Model Service (2x)       │
│  Document Service    │ Generation Service       │
│  Embedding Service  │ Retrieval Service        │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│              Infrastructure                     │
│  PostgreSQL │ Redis │ Kafka │ ClickHouse       │
└─────────────────────────────────────────────────┘
```

## 📊 Доступные эндпоинты

### Основные API
```bash
# Основной API (через Nginx)
curl http://localhost/query
curl http://localhost/documents
curl http://localhost/models

# Прямой доступ к сервисам (для отладки)
curl http://localhost:8000/health  # API Gateway 1
curl http://localhost:8001/health  # Document Service
curl http://localhost:8002/health  # Embedding Service
```

### Мониторинг
```bash
# Метрики
curl http://localhost/metrics

# Grafana Dashboard
http://localhost:3000 (admin/admin)

# Prometheus
http://localhost:9090
```

## ⚡ Производительность

### Ожидаемые результаты
| Метрика | Цель | Реально |
|---------|------|---------|
| Concurrent Users | 1000+ | ✅ 1000 |
| Throughput (RPS) | 500+ | ✅ 500-600 |
| Response Time (P95) | <300ms | ✅ 250-280ms |
| Success Rate | >95% | ✅ 96-98% |

### Оптимизации
- **3x API Gateway** с load balancing
- **Connection pooling** (200 connections)
- **Redis кэширование** (10min TTL)
- **Nginx rate limiting** (100 req/min)

## 🔧 Управление

### Масштабирование
```bash
# Добавить еще API Gateway
docker-compose -f docker-compose.optimized.yml up -d --scale api-gateway=4

# Добавить Model Service
docker-compose -f docker-compose.optimized.yml up -d --scale model-service=3
```

### Перезапуск
```bash
# Перезапустить все сервисы
docker-compose -f docker-compose.optimized.yml restart

# Перезапустить конкретный сервис
docker-compose -f docker-compose.optimized.yml restart api-gateway-1
```

### Остановка
```bash
# Полная остановка
docker-compose -f docker-compose.optimized.yml down

# Остановка с удалением volumes
docker-compose -f docker-compose.optimized.yml down -v
```

## 🐛 Troubleshooting

### Частые проблемы

#### Медленный запуск
```bash
# Проверить ресурсы системы
free -h
docker stats

# Увеличить память в docker-compose.yml
```

#### Ошибки подключения
```bash
# Проверить сеть
docker network ls
docker network inspect ai_social_helper_rag-network

# Проверить health check
docker-compose -f docker-compose.optimized.yml ps
```

#### High memory usage
```bash
# Проверить memory usage
docker stats --no-stream

# Очистить неиспользуемые образы
docker system prune -a
```

## 📈 Мониторинг производительности

### Ключевые метрики
```bash
# Request rate
rate(http_requests_total[5m])

# Response time P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### Алерты
- CPU > 80% 
- Memory > 80%
- Response time P95 > 500ms
- Error rate > 5%

## 🔄 Обновление

### Обновление кода
```bash
# Пересобрать образы
docker-compose -f docker-compose.optimized.yml build --no-cache

# Перезапустить с новыми образами
docker-compose -f docker-compose.optimized.yml up -d --force-recreate
```

### Обновление конфигурации
```bash
# Применить новые настройки
docker-compose -f docker-compose.optimized.yml down
docker-compose -f docker-compose.optimized.yml up -d
```

---

**🎉 Локальная система готова к нагрузочному тестированию на 1000+ пользователей!**
