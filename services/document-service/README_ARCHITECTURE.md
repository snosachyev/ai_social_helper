# Document Service - Clean Architecture

## Обзор архитектуры

Сервис реорганизован по принципам чистой архитектуры (Clean Architecture) с разделением на слои:

```
services/document-service/
├── src/
│   ├── domain/                 # Бизнес-логика и сущности
│   │   ├── entities/          # Domain сущности
│   │   ├── repositories/      # Интерфейсы репозиториев
│   │   └── services/          # Domain сервисы
│   ├── application/           # Приложенская логика
│   │   ├── use_cases/         # Use cases (бизнес-сценарии)
│   │   └── services/          # DI контейнер
│   ├── infrastructure/        # Внешние зависимости
│   │   ├── database/          # Модели данных
│   │   ├── repositories/      # Реализации репозиториев
│   │   └── external/          # Внешние сервисы
│   └── presentation/          # API слой
│       └── api/               # FastAPI endpoints
├── tests/                     # Тесты
│   ├── unit/                  # Unit тесты
│   ├── integration/          # Integration тесты
│   └── fixtures/              # Test fixtures
├── main.py                    # Точка входа
├── requirements.txt           # Все зависимости (включая тестовые)
├── Dockerfile                 # Docker для сервиса и тестов
└── README_ARCHITECTURE.md     # Этот файл
```

## Слои архитектуры

### Domain Layer
- **Entities**: `Document`, `TextChunk`, `ProcessingResult`
- **Repository Interfaces**: `DocumentRepository`, `ChunkRepository`, `CacheRepository`
- **Domain Services**: `DocumentTextExtractor`, `TextChunker`, `FileValidator`

### Application Layer
- **Use Cases**: `UploadDocumentUseCase`, `GetDocumentUseCase`, `ListDocumentsUseCase`
- **DI Container**: Внедрение зависимостей

### Infrastructure Layer
- **Database Models**: SQLAlchemy модели `DocumentDB`, `ChunkDB`
- **Repository Implementations**: `SqlAlchemyDocumentRepository`, `RedisCacheRepository`
- **External Services**: `DocumentTextExtractorImpl`, `TextChunkerImpl`

### Presentation Layer
- **API Routes**: FastAPI endpoints с использованием use cases

## Пример Use Case

```python
@dataclass
class UploadDocumentRequest:
    file: BinaryIO
    filename: str
    content: bytes
    chunk_size: int = 1000
    overlap: int = 200

class UploadDocumentUseCase:
    def __init__(self, document_repo, chunk_repo, cache_repo, 
                 text_extractor, text_chunker, file_validator):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        # ... другие зависимости
    
    async def execute(self, request: UploadDocumentRequest) -> UploadDocumentResponse:
        # Валидация файла
        if not self.file_validator.validate_file_type(request.filename):
            raise ValueError("Unsupported file type")
        
        # Сохранение документа
        document = await self.document_repo.save(document)
        
        # Извлечение текста
        text = await self.text_extractor.extract_text(file_path, file_type)
        
        # Чанкинг текста
        chunk_texts = self.text_chunker.chunk_text(text)
        
        # Сохранение чанков
        chunks = [TextChunk(...) for chunk_text in chunk_texts]
        await self.chunk_repo.save_batch(chunks)
        
        return UploadDocumentResponse(...)
```

## Пример обновленного endpoint

```python
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    container: DIContainer = Depends(get_di_container)
):
    try:
        content = await file.read()
        request = UploadDocumentRequest(
            file=file.file,
            filename=file.filename,
            content=content
        )
        
        use_case = container.get_upload_document_use_case()
        response = await use_case.execute(request)
        
        return BaseResponse(
            success=True,
            message=f"Document uploaded successfully. Generated {response.chunk_count} chunks."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Тестирование

### Структура тестов

**Unit тесты** (`tests/unit/`):
- Тестируют use cases в изоляции
- Используют mock объекты для внешних зависимостей
- Пример: `test_upload_document_success()`

**Integration тесты** (`tests/integration/`):
- Используют реальные зависимости (база данных, Redis)
- Пример: `test_health_check()`, `test_file_validator_supported_types()`

### Запуск тестов в Docker контейнере

```bash
# Сборка Docker образа
docker compose build document-service

# Запуск всех тестов
docker run --rm rag_system-document-service python -m pytest tests/ -v

# Запуск только unit тестов
docker run --rm rag_system-document-service python -m pytest tests/unit/ -v

# Запуск только integration тестов
docker run --rm rag_system-document-service python -m pytest tests/integration/ -v

# Запуск с покрытием кода
docker run --rm rag_system-document-service python -m pytest tests/ --cov=src --cov-report=html
```

### Локальный запуск тестов

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск unit тестов
pytest tests/unit/ -v

# Запуск integration тестов (требуются запущенные PostgreSQL и Redis)
pytest tests/integration/ -v

# Запуск всех тестов
pytest tests/ -v

# Запуск с покрытием
pytest tests/ --cov=src --cov-report=html
```

## Преимущества архитектуры

1. **Разделение ответственности**: Каждый слой имеет четкую зону ответственности
2. **Тестируемость**: Легко мокать зависимости и писать unit тесты
3. **Расширяемость**: Проще добавлять новые use cases и репозитории
4. **Поддержка**: Бизнес-логика изолирована от инфраструктуры

## Запуск сервиса

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервиса
python main.py

# Или через Docker
docker build -t document-service .
docker run -p 8001:8001 document-service
```

## API Endpoints

Все endpoints доступны с префиксом `/api/v1/`:

- `POST /api/v1/documents/upload` - Загрузка документа
- `GET /api/v1/documents/{document_id}` - Получение метаданных документа
- `GET /api/v1/documents` - Список документов
- `GET /api/v1/documents/{document_id}/chunks` - Получение чанков документа
- `GET /api/v1/health` - Проверка здоровья сервиса

## Migration со старой архитектуры

✅ **Завершено**: Старый код заменен на новую чистую архитектуру
- `main.py` содержит новую архитектуру
- Все endpoints перенесены на `/api/v1/...`
- Бизнес-логика вынесена в use cases
- Добавлены тесты для Docker окружения
