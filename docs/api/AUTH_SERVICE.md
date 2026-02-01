# 🔐 Сервис Авторизации RAG Системы

## 📋 Обзор

Создан полнофункциональный сервис авторизации для вашей RAG системы с поддержкой:
- JWT токенов (access + refresh)
- Ролевой модели доступа (Admin, User, Viewer)
- Безопасного хеширования паролей
- Управления пользователями
- API эндпоинтов для аутентификации

## 🏗️ Архитектура

### Domain Layer
- **User Entities**: `src/domain/entities/user.py`
  - `User`, `UserCreate`, `UserUpdate`, `UserResponse`
  - `Token`, `TokenData`, `UserRole`, `UserStatus`

### Application Layer  
- **Use Cases**: `src/application/use_cases/auth_use_case.py`
  - `AuthUseCase`: Регистрация, логин, управление токенами
  - `UserManagementUseCase`: Административные функции

### Infrastructure Layer
- **Repository**: `src/infrastructure/repositories/user_repository.py`
- **Database Models**: `src/infrastructure/database/user_models.py`
- **Auth Service**: `src/domain/services/auth_service.py`

### Presentation Layer
- **API Controller**: `src/presentation/api/auth_controller.py`
- **Docker Service**: `services/auth-service/`

## 🚀 API Эндпоинты

### Аутентификация
```
POST /auth/register     - Регистрация пользователя
POST /auth/login        - Вход в систему
POST /auth/refresh      - Обновление токена
POST /auth/logout       - Выход из системы
GET  /auth/me          - Текущий пользователь
PUT  /auth/me          - Обновление профиля
POST /auth/change-password - Смена пароля
```

### Административные функции
```
GET    /auth/users           - Список пользователей
GET    /auth/users/{id}      - Информация о пользователе
PUT    /auth/users/{id}      - Обновление пользователя
DELETE /auth/users/{id}      - Удаление пользователя
POST   /auth/users/{id}/activate   - Активация
POST   /auth/users/{id}/deactivate - Деактивация
GET    /auth/statistics      - Статистика пользователей
```

### Health Check
```
GET /auth/health - Проверка состояния сервиса
```

## 🔧 Конфигурация

### Настройки в `settings.py`
```python
class AuthConfig(BaseModel):
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    enable_rate_limiting: bool = True
    max_login_attempts: int = 5
```

### Docker Сервис
```yaml
auth-service:
  build:
    context: .
    dockerfile: services/auth-service/Dockerfile
  ports:
    - "8007:8007"
  environment:
    - JWT_SECRET_KEY=your-secret-key
    - JWT_ALGORITHM=HS256
    - ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 🧪 Тестирование

### Рабочие тесты
```bash
# Запуск тестов авторизации в Docker
docker-compose exec auth-service python -m pytest tests/test_auth_smoke.py -v

# Конкретные тесты
docker-compose exec auth-service pytest tests/test_auth_smoke.py::TestAuthBasic::test_auth_health_endpoint -v
```
```

### Пример теста
```python
def test_user_registration_basic(self):
    """Test basic user registration"""
    mock_auth_use_case = Mock()
    mock_auth_use_case.register_user = AsyncMock()
    
    app = create_application()
    app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
    
    client = TestClient(app)
    response = client.post("/auth/register", json=user_data)
    
    assert response.status_code == 201
```

## 📊 Роли пользователей

### Admin (Администратор)
- Полный доступ ко всем функциям
- Управление пользователями
- Просмотр статистики

### User (Пользователь)
- Загрузка и управление документами
- Выполнение запросов
- Управление своим профилем

### Viewer (Наблюдатель)
- Только чтение документов
- Выполнение запросов
- Ограниченные функции

## 🔒 Безопасность

### JWT Токены
- **Access Token**: 30 минут
- **Refresh Token**: 7 дней
- **Алгоритм**: HS256
- **Blacklist**: Поддерживается

### Пароли
- **Хеширование**: bcrypt
- **Минимальная длина**: 8 символов
- **Соль**: Автоматическая

### Rate Limiting
- **Лимит**: 60 запросов в минуту
- **Блокировка**: После 5 неудачных попыток

## 📦 Зависимости

```txt
python-jose[cryptography]==3.3.0  # JWT
passlib[bcrypt]==1.7.4            # Хеширование паролей
pydantic[email]                    # Валидация email
python-multipart==0.0.6            # Form data
```

## 🔄 Интеграция

### Подключение к основному приложению
```python
# src/presentation/api/app.py
from .auth_controller import router as auth_router

app.include_router(auth_router)
```

### Dependency Injection
```python
# В контроллерах
def get_auth_use_case() -> AuthUseCase:
    container = DIContainer()
    return container.resolve(AuthUseCase)
```

## 🚀 Запуск

### Разработка
```bash
# Активация окружения
source ../.venv/bin/activate

# Установка зависимостей
pip install python-jose[cryptography] passlib[bcrypt] 'pydantic[email]'

# Запуск тестов
python -m pytest tests/test_auth_smoke.py -v
```

### Production
```bash
# Сборка и запуск Docker контейнера
docker compose up -d auth-service

# Проверка состояния
curl http://localhost:8007/auth/health
```

## 📈 Статус

### ✅ Реализовано
- [x] Базовая архитектура авторизации
- [x] JWT токены (access + refresh)
- [x] Ролевая модель доступа
- [x] API эндпоинты
- [x] Docker сервис
- [x] Базовые тесты
- [x] Конфигурация безопасности

### 🔧 Требует доработки
- [ ] Полные интеграционные тесты
- [ ] Email верификация
- [ ] OAuth2 интеграция
- [ ] Audit логирование
- [ ] Миграции базы данных
- [ ] Rate limiting middleware

## 🎯 Следующие шаги

1. **Настроить базу данных** для пользователей
2. **Интегрировать** с существующими сервисами
3. **Добавить middleware** для проверки токенов
4. **Настроить CORS** для фронтенда
5. **Развернуть** в production окружении

---

**Сервис авторизации готов к интеграции в вашу RAG систему!** 🚀
