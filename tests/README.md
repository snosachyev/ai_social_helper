# RAG System Tests

This directory contains comprehensive tests for the RAG (Retrieval-Augmented Generation) system, focusing on document upload, text generation, and query functionality.

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── utils.py                 # Test utilities and helper functions
├── integration/
│   └── test_query_generate_integration.py  # Интеграционные тесты для query/generate
├── presentation/
│   └── api/
│       └── test_query_controller.py      # Unit тесты для контроллера
└── README.md               # Этот файл
```

## Интеграционные тесты

### Запуск интеграционных тестов

```bash
# Простая команда для запуска всех интеграционных тестов
python run_integration_tests.py

# Или через pytest
pytest tests/integration/ -v
```

### Что проверяют интеграционные тесты

1. **Аутентификация**
   - ✅ Получение токена работает
   - ✅ Эндпоинты `/query` и `/generate` требуют аутентификацию
   - ✅ Невалидные токены отклоняются

2. **Query эндпоинт (`/query`)**
   - ✅ Работает с валидным токеном
   - ✅ Отклоняет запросы без токена (403)
   - ✅ Принимает различные типы запросов
   - ✅ Обрабатывает разные параметры

3. **Generate эндпоинт (`/generate`)**
   - ✅ Работает с валидным токеном
   - ✅ Отклоняет запросы без токена (403)
   - ✅ Работает с минимальными данными

4. **Здоровье сервисов**
   - ✅ Auth service (порт 8007) здоров
   - ✅ Embedding service (порт 8002) здоров
   - ✅ Retrieval service (порт 8004) здоров

5. **End-to-end workflow**
   - ✅ Полный цикл от аутентификации до ответа

### Требования для запуска

1. **Запущенные сервисы:**
   ```bash
   docker compose up -d
   ```

2. **Доступные эндпоинты:**
   - Auth service: `http://localhost:8007`
   - API Gateway: `http://localhost:8000`
   - Embedding service: `http://localhost:8002`
   - Retrieval service: `http://localhost:8004`

## Unit тесты

Unit тесты проверяют отдельные компоненты с использованием моков:

```bash
# Запуск unit тестов
pytest tests/presentation/api/ -v
```

### Покрытие тестами

- ✅ Успешные сценарии
- ✅ Обработка ошибок
- ✅ Валидация входных данных
- ✅ Значения по умолчанию
- ✅ Асинхронная обработка

## Пример использования

```python
# Получение токена
import httpx

async def get_token():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8007/auth/login",
            json={"email": "test@example.com", "password": "test"}
        )
        return response.json()["access_token"]

# Использование токена для запроса
async def query_with_auth(token):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/query",
            json={"query": "What is machine learning?", "top_k": 3},
            headers=headers
        )
        return response.json()
```

## Решенные проблемы

1. **Аутентификация:** Исправлена работа с токенами
2. **Локальные модели:** Настроено использование локальных embedding моделей
3. **Интеграция сервисов:** Исправлено взаимодействие между retrieval и embedding сервисами
4. **Формат запросов:** Исправлены параметры запросов (query string vs JSON body)
├── pytest.ini              # Pytest configuration file
├── requirements-test.txt   # Test-specific dependencies
├── README.md               # This file
└── presentation/
    └── api/
        ├── __init__.py
        ├── test_document_controller.py  # Document endpoint tests
        └── test_query_controller.py     # Query endpoint tests
```

## Test Coverage

### Document Controller Tests (`test_document_controller.py`)

- **Document Upload**: 
  - Successful upload with various file types
  - Encoding error handling
  - File type validation
  - Use case exception handling
  - Async upload testing

- **Document Retrieval**:
  - Get document by ID
  - Document not found scenarios
  - Invalid UUID handling
  - Exception handling

- **Document Listing**:
  - Pagination support
  - Status filtering
  - Invalid parameter handling

- **Document Management**:
  - Delete document functionality
  - Status updates
  - Error scenarios

### Query Controller Tests (`test_query_controller.py`)

- **Query Processing**:
  - Semantic search functionality
  - Different query types (semantic, hybrid, keyword)
  - Filter and metadata handling
  - Guard result validation

- **Text Generation**:
  - Response generation with context
  - Model parameter validation
  - Context format validation
  - Guard result checking

- **Query Utilities**:
  - Query suggestions
  - Query history
  - Health checks

## Running Tests

### Prerequisites

1. Install test dependencies:
```bash
pip install -r tests/requirements-test.txt
```

2. Ensure the main application dependencies are installed:
```bash
pip install -r requirements.txt
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/presentation/api/test_document_controller.py

# Run specific test class
pytest tests/presentation/api/test_document_controller.py::TestDocumentUpload

# Run specific test method
pytest tests/presentation/api/test_document_controller.py::TestDocumentUpload::test_upload_document_success
```

### Advanced Test Execution

```bash
# Run with coverage
pytest --cov=src --cov-report=html

# Run in parallel
pytest -n auto

# Run with timeout
pytest --timeout=300

# Run performance tests
pytest -m performance

# Run only smoke tests
pytest -m smoke

# Run async tests specifically
pytest -m async_test
```

### Test Markers

The tests use the following pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.async_test`: Async tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.smoke`: Smoke tests
- `@pytest.mark.api`: API tests
- `@pytest.mark.document`: Document-related tests
- `@pytest.mark.query`: Query-related tests
- `@pytest.mark.generation`: Text generation tests

## Test Fixtures

### Main Fixtures

- `app`: FastAPI application instance
- `client`: TestClient for synchronous testing
- `async_client`: AsyncClient for asynchronous testing
- `mock_document_use_case`: Mocked document use case
- `mock_query_use_case`: Mocked query use case
- `mock_tracing_service`: Mocked tracing service

### Data Fixtures

- `sample_document`: Sample document entity
- `sample_query_request`: Sample query request
- `sample_generation_request`: Sample generation request
- `sample_text_file`: Sample text content
- Various response fixtures for different scenarios

## Test Utilities

The `utils.py` file provides helper functions for:

- Creating temporary files
- Generating sample data
- Creating test scenarios
- Performance profiling
- Mock response building
- Validation utilities

### Example Usage

```python
from tests.utils import create_temp_file, generate_sample_document_text

# Create a temporary file for testing
temp_file = create_temp_file("test content")
try:
    # Use the file in your test
    pass
finally:
    cleanup_temp_file(temp_file)

# Generate sample document text
sample_text = generate_sample_document_text(length=1000)
```

## Configuration

### Pytest Configuration

The `pytest.ini` file contains:

- Test discovery settings
- Output formatting options
- Marker definitions
- Logging configuration
- Coverage settings

### Environment Variables

You can set these environment variables for testing:

```bash
# Set test database URL
export TEST_DATABASE_URL="postgresql://test:test@localhost/test_db"

# Set log level
export LOG_LEVEL="DEBUG"

# Disable external services for testing
export DISABLE_EXTERNAL_SERVICES="true"
```

## Best Practices

### Writing New Tests

1. **Use descriptive names**: Test method names should clearly describe what they test
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Use fixtures**: Leverage existing fixtures for consistency
4. **Mock external dependencies**: Use mocks to isolate tests
5. **Test both success and failure cases**: Cover all scenarios
6. **Add appropriate markers**: Use pytest markers for categorization

### Example Test Structure

```python
class TestNewFeature:
    """Test new feature functionality"""
    
    def test_new_feature_success(self, client, mock_service):
        """Test successful new feature execution"""
        # Arrange
        mock_service.new_method.return_value = expected_result
        
        # Act
        response = client.post("/new-endpoint", json=test_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == expected_result
        mock_service.new_method.assert_called_once_with(test_data)
    
    def test_new_feature_failure(self, client, mock_service):
        """Test new feature failure scenario"""
        # Arrange
        mock_service.new_method.side_effect = Exception("Service error")
        
        # Act
        response = client.post("/new-endpoint", json=test_data)
        
        # Assert
        assert response.status_code == 500
        assert "Service error" in response.json()["detail"]
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r tests/requirements-test.txt
    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running tests from the project root
2. **Async test failures**: Make sure to use `@pytest.mark.asyncio`
3. **Mock not working**: Check that patches are correctly applied
4. **Database connection issues**: Set up test database properly

### Debugging Tests

```bash
# Run with pdb debugger
pytest --pdb

# Stop on first failure
pytest -x

# Run with local debugging
pytest --tb=long --no-header

# Show slowest tests
pytest --durations=10
```

## Contributing

When adding new tests:

1. Follow the existing code style
2. Add appropriate docstrings
3. Use existing fixtures when possible
4. Add new fixtures to `conftest.py` if needed
5. Update this README if adding new test categories
6. Ensure all tests pass before submitting

## Performance Testing

For performance testing, use the built-in benchmarking:

```bash
# Run performance benchmarks
pytest --benchmark-only

# Generate benchmark report
pytest --benchmark-only --benchmark-json=benchmark.json
```

The `PerformanceProfiler` class in `utils.py` can also be used for custom performance measurements.
