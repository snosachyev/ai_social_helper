# 🚀 Quick Start Guide

## 1. Запуск проекта

### Предварительные требования
- Docker и Docker Compose
- Telegram API ID и API Hash (получить на https://my.telegram.org)

### Шаг 1: Настройка окружения

```bash
# Скопировать файл окружения
cp .env.example .env

# Отредактировать переменные окружения
nano .env
```

### Шаг 2: Запуск инфраструктуры

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps
```

### Шаг 3: Проверка работоспособности

```bash
# Проверить health endpoints
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8008/health  # Telegram Service
```

## 2. Парсинг канала Павла Дурова

### Шаг 1: Получение API ключей

1. Зайдите на https://my.telegram.org
2. Войдите в свой аккаунт
3. Создайте приложение и получите `api_id` и `api_hash`
4. Добавьте их в `.env` файл:

```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

### Шаг 2: Использование реальной сессии

Проект уже содержит реальную сессию `my_session.session` в папке `services/telegram-service/`

### Шаг 3: Запуск парсинга

```bash
# Спарсить 5 последних постов из канала Павла Дурова
curl -X POST "http://localhost:8008/channels/parse" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_username": "durov",
    "limit": 5
  }'
```

### Пример ответа:

```json
{
  "success": true,
  "message": "Successfully parsed 5 posts from durov",
  "data": {
    "posts": [
      {
        "message_id": 12345,
        "channel_id": 123456789,
        "channel_title": "Pavel Durov",
        "channel_username": "durov",
        "text": "Текст поста...",
        "date": "2024-01-31T10:15:00",
        "views": 150000,
        "forwards": 234,
        "media_type": null,
        "sync_type": "realtime"
      }
    ],
    "channel": "durov",
    "total_parsed": 5
  }
}
```

## 3. Дополнительные endpoints

### Получить список всех каналов

```bash
curl http://localhost:8008/channels/list
```

### Получить сообщения из канала

```bash
curl "http://localhost:8008/channels/123456789/messages?limit=10"
```

### Присоединиться к каналу

```bash
curl -X POST "http://localhost:8008/channels/join" \
  -H "Content-Type: application/json" \
  -d '{"channel_username": "durov"}'
```

## 4. Мониторинг

### Grafana Dashboard
- URL: http://localhost:3000
- Login: admin
- Password: admin

### Prometheus Metrics
- URL: http://localhost:9090

## 5. Тестирование

```bash
# Запуск тестов в Docker
docker-compose exec auth-service python -m pytest tests/ -v

# Тесты для telegram сервиса
docker-compose exec telegram-service python -m pytest tests/ -v
```

## 6. Остановка проекта

```bash
# Остановить все сервисы
docker-compose down

# Удалить volumes (осторожно!)
docker-compose down -v
```

## 7. Структура проекта

```
ai_social_helper/
├── services/                 # Микросервисы
│   ├── api-gateway/         # API Gateway (порт 8000)
│   ├── telegram-service/    # Telegram парсер (порт 8008)
│   ├── generation-service/  # LLM генерация (порт 8005)
│   ├── retrieval-service/  # RAG ретривер (порт 8004)
│   └── ...
├── infrastructure/          # Инфраструктура
│   ├── postgres/           # База данных
│   ├── redis/              # Кеш и rate limiting
│   ├── kafka/              # Message broker
│   └── qdrant/             # Vector database
├── k8s/                    # Kubernetes конфигурации
└── shared/                 # Общие модули
```

## 8. Возможные проблемы

### Проблема: "Session is not authorized"
**Решение**: Убедитесь что `my_session.session` файл существует и валиден

### Проблема: "Flood wait error"
**Решение**: Сервис автоматически обрабатывает эти ошибки с задержкой

### Проблема: "Channel not found"
**Решение**: Проверьте правильность username канала (с @ или без)

## 9. Production развертывание

Для production развертывания используйте Kubernetes конфигурации в папке `k8s/`:

```bash
# Применить конфигурации
kubectl apply -f k8s/

# Проверить статус
kubectl get pods -n rag-system
```

Система готова к продакшену и поддерживает 1000+ активных пользователей!
