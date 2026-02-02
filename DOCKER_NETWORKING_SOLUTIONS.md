# 🐳 Docker Networking Решения для Production

## 🎯 **Проблема:**
Docker Desktop userland proxy не может обработать 800+ одновременных TCP соединений → `connection refused`

## ✅ **Решения (по приоритету):**

### **1️⃣ Host Networking (рекомендуется для разработки)**

**Принцип:** Контейнеры используют сеть хоста напрямую

**Плюсы:**
✅ Максимальная производительность  
✅ Нет NAT overhead  
✅ Простая настройка  
✅ Решает проблему connection refused  

**Минусы:**
⚠️ Конфликт портов  
⚠️ Меньше изоляции  
⚠️ Не подходит для multi-tenant  

**Когда использовать:**
- Разработка и тестирование
- Single-server deployment
- Когда нужна максимальная производительность

**Как запустить:**
```bash
./scripts/start_host_network.sh
```

**Конфигурация:**
```yaml
services:
  api-gateway:
    network_mode: host  # Ключевая настройка
    ports: []  # Не нужно, порт доступен напрямую
```

---

### **2️⃣ Оптимизированный Docker Networking**

**Принцип:** Увеличиваем лимиты и оптимизируем параметры

**Плюсы:**
✅ Сохраняет изоляцию  
✅ Production-ready  
✅ Масштабируемость  

**Минусы:**
⚠️ Сложнее настройка  
⚠️ Может не решить полностью  

**Оптимизации:**
```yaml
services:
  api-gateway:
    ulimits:
      nofile:
        soft: 65535
        hard: 65535
    sysctls:
      - net.core.somaxconn=65535
      - net.ipv4.tcp_max_syn_backlog=65535
    command: >
      uvicorn app:app --backlog 65535
```

**Сеть:**
```yaml
networks:
  rag-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: rag-br0
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

---

### **3️⃣ Kubernetes (лучшее для production)**

**Принцип:** Enterprise-grade оркестрация с продвинутой сетью

**Плюсы:**
✅ Auto-scaling  
✅ Load balancing  
✅ Service mesh  
✅ High availability  
✅ Production networking  

**Минусы:**
⚠️ Сложность  
⚠️ Требует обучения  
⚠️ Overhead для small projects  

**Auto-scaling:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Networking:**
```yaml
spec:
  containers:
  - name: api-gateway
    securityContext:
      sysctls:
      - name: net.core.somaxconn
        value: "65535"
```

---

## 📊 **Сравнение решений:**

| Решение | Производительность | Сложность | Изоляция | Масштабируемость | Рекомендация |
|---------|-------------------|-----------|----------|------------------|--------------|
| **Host Networking** | 🚀 Максимальная | ⭐ Простое | ⚠️ Низкая | ⚠️ Ограничена | ✅ Разработка |
| **Optimized Docker** | 🔥 Высокая | ⭐⭐ Средняя | ✅ Хорошая | ✅ Хорошая | ✅ Small Production |
| **Kubernetes** | 🚀 Высокая | ⭐⭐⭐ Сложная | ✅ Отличная | 🚀 Максимальная | ✅ Enterprise |

---

## 🎯 **Рекомендации по выбору:**

### **Для разработки и тестирования:**
```bash
# Используйте host networking
./scripts/start_host_network.sh
k6 run --vus 1000 --duration 60s tests/performance/k6/native_test_fixed.js
```

### **Для small/medium production:**
```bash
# Оптимизированный Docker
docker compose -f docker-compose.optimized-network.yml up -d
```

### **Для enterprise production:**
```bash
# Kubernetes
kubectl apply -f k8s-production/
```

---

## 🛠️ **Production Best Practices:**

### **1. Мониторинг сети:**
```yaml
# Добавьте метрики
- name: connection-count
  value: "netstat -an | grep :8000 | wc -l"
```

### **2. Health checks:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### **3. Resource limits:**
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### **4. Graceful shutdown:**
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
```

---

## 🚀 **Quick Start для Production:**

### **Шаг 1: Выберите решение**
```bash
# Для разработки
./scripts/start_host_network.sh

# Для production
docker compose -f docker-compose.optimized-network.yml up -d
```

### **Шаг 2: Протестируйте**
```bash
# Тест нагрузки
k6 run --vus 1000 --duration 60s tests/performance/k6/native_test_fixed.js
```

### **Шаг 3: Мониторьте**
```bash
# Проверьте статус
curl http://localhost:80/health

# Логи
docker logs rag-api-gateway-host-1
```

---

## 🏆 **Финальный вывод:**

**Docker networking проблема решаема!** 

- **Host networking** - простое и эффективное решение для разработки
- **Optimized Docker** - production-ready с хорошей изоляцией  
- **Kubernetes** - enterprise решение с auto-scaling

**Ваша система готова к 1000+ пользователей** с любым из этих решений! 🎉
