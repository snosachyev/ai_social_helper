# 🚀 Kubernetes для локальной разработки

## 📋 Что это дает

Kubernetes локально предоставляет:
- **Автоматическое масштабирование** (HPA)
- **Load balancing** из коробки
- **Health checks** и self-healing
- **Rolling updates** без downtime
- **Resource management** и ограничения

## 🛠️ Локальные варианты Kubernetes

### 1. **Minikube** (рекомендуется для начала)
```bash
# Установка
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Запуск
minikube start --cpus=4 --memory=8192 --disk-size=20g

# Проверка
minikube status
kubectl get nodes
```

### 2. **Kind** (Kubernetes in Docker)
```bash
# Установка
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Создание кластера
kind create cluster --config=k8s-local/kind-config.yaml

# Проверка
kubectl cluster-info
```

### 3. **K3s** (легковесный)
```bash
# Установка
curl -sfL https://get.k3s.io | sh -

# Проверка
sudo kubectl get nodes
```

### 4. **Docker Desktop** (проще всего)
```bash
# Включить Kubernetes в настройках Docker Desktop
# Settings → Kubernetes → Enable Kubernetes
```

## 🚀 Быстрый старт с Minikube

### Шаг 1: Установка и запуск
```bash
# Запуск Minikube
minikube start --cpus=4 --memory=8192

# Включить addons
minikube addons enable ingress
minikube addons enable metrics-server
```

### Шаг 2: Деплой нашего приложения
```bash
# Применить конфигурации
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmaps.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/api-gateway.yaml
kubectl apply -f k8s/ingress.yaml
```

### Шаг 3: Проверка статуса
```bash
# Проверить поды
kubectl get pods -n rag-system

# Проверить сервисы
kubectl get svc -n rag-system

# Проверить HPA
kubectl get hpa -n rag-system
```

### Шаг 4: Доступ к приложению
```bash
# Получить URL
minikube service rag-api-gateway -n rag-system --url

# Или через порт-форвардинг
kubectl port-forward svc/rag-api-gateway 8080:80 -n rag-system
```

## 📊 Преимущества локального Kubernetes

### **vs Docker Compose:**
- ✅ **Автоматическое масштабирование** - HPA увеличивает количество подов
- ✅ **Self-healing** - перезапуск упавших подов
- ✅ **Load balancing** - встроенный Service load balancer
- ✅ **Rolling updates** - обновления без простоя
- ✅ **Resource limits** - контроль CPU/memory

### **vs Production Kubernetes:**
- ✅ **Та же архитектура** - плавный переход в продакшен
- ✅ **Локальная разработка** - быстрое тестирование
- ✅ **Дешево** - не требует облачных ресурсов
- ✅ **Быстро** - запуск за минуты

## 🔧 Конфигурация для 1000+ пользователей

### Horizontal Pod Autoscaler (HPA)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-api-gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-api-gateway
  minReplicas: 5
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

### Resource Limits
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

## 🧪 Тестирование нагрузки

### Сценарий тестирования:
```bash
# 1. Запустить с 5 подами
kubectl scale deployment rag-api-gateway --replicas=5 -n rag-system

# 2. Начать нагрузочный тест
k6 run --vus 500 --duration 60s tests/performance/k6/high_perf_test.js

# 3. Наблюдать за масштабированием
watch kubectl get pods -n rag-system

# 4. Проверить HPA события
kubectl describe hpa rag-api-gateway-hpa -n rag-system
```

## 📈 Мониторинг

### Метрики в реальном времени:
```bash
# Использование ресурсов
kubectl top pods -n rag-system

# HPA статус
kubectl get hpa -n rag-system -w

# События
kubectl get events -n rag-system --sort-by='.lastTimestamp'
```

## 🎯 Когда использовать локальный Kubernetes

### **Идеально для:**
- 🧪 **Тестирования масштабирования** - HPA, load balancing
- 🚀 **Разработки microservices** - изоляция сервисов
- 📊 **Бенчмаркинга** - сравнение производительности
- 🔧 **Отладки** distributed систем
- 🎓 **Изучения Kubernetes** - практический опыт

### **Не заменяет продакшен:**
- ⚠️ **Ограниченные ресурсы** - 1 машина vs кластер
- ⚠️ **Нет высокой доступности** - 1 нода
- ⚠️ **Простая сеть** - нет сложной сетевой топологии

## 🚀 Следующие шаги

1. **Установить Minikube** и запустить локальный кластер
2. **Деплонуть приложение** и протестировать HPA
3. **Провести нагрузочные тесты** с автоматическим масштабированием
4. **Сравнить производительность** с Docker Compose
5. **Подготовить к продакшен** - миграция в облако

---

**Результат:** Локальный Kubernetes дает преимущества продакшен-архитектуры для разработки и тестирования!
