# 🧪 Testing Guide for RAG System

This guide provides comprehensive information about the testing strategy and how to run tests for the RAG system.

## 📋 Table of Contents

- [Test Types](#test-types)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [CI/CD Pipeline](#cicd-pipeline)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## 🎯 Test Types

### Unit Tests
- **Purpose**: Test individual components in isolation
- **Location**: `tests/unit/`
- **Coverage Target**: 90%+
- **Run Time**: < 2 minutes

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/domain/test_document_entities.py -v
```

### Integration Tests
- **Purpose**: Test interaction between components
- **Location**: `tests/integration/`
- **Coverage Target**: 80%+
- **Run Time**: 5-10 minutes

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with timeout
pytest tests/integration/ --timeout=300

# Run specific integration test
pytest tests/integration/api/test_document_flow.py -v
```

### Contract Tests
- **Purpose**: Test API contracts and service interfaces
- **Location**: `tests/contract/`
- **Coverage Target**: 100%
- **Run Time**: 3-5 minutes

```bash
# Run all contract tests
pytest tests/contract/ -v

# Run API contracts only
pytest tests/contract/api_contracts/ -v

# Run service contracts only
pytest tests/contract/service_contracts/ -v
```

### Performance Tests
- **Purpose**: Test system performance under load
- **Location**: `tests/performance/`
- **Run Time**: 10-30 minutes

```bash
# Run performance tests
pytest tests/performance/ -v

# Run with benchmarking
pytest tests/performance/ --benchmark-only

# Generate benchmark report
pytest tests/performance/ --benchmark-json=benchmark.json
```

## 🚀 Running Tests

### Prerequisites

1. **Install dependencies**:
```bash
pip install -r requirements.txt
pip install -r tests/requirements-test.txt
```

2. **Start test services** (for integration/contract tests):
```bash
docker-compose -f docker-compose.test.yml up -d
```

3. **Wait for services to be ready**:
```bash
# Check service health
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8001/health  # Document Service
curl http://localhost:8002/health  # Embedding Service
```

### Running Different Test Suites

#### Quick Development Tests
```bash
# Run unit tests only (fastest)
pytest tests/unit/ -v --tb=short

# Run with specific markers
pytest -m "not slow" -v
```

#### Full Test Suite
```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=xml

# Run in parallel
pytest -n auto
```

#### Specific Test Categories
```bash
# Run only smoke tests
pytest -m smoke -v

# Run only API tests
pytest -m api -v

# Run only document tests
pytest -m document -v

# Run only query tests
pytest -m query -v
```

### Test Markers

The test suite uses the following pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.contract`: Contract tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.smoke`: Smoke tests
- `@pytest.mark.api`: API tests
- `@pytest.mark.document`: Document-related tests
- `@pytest.mark.query`: Query-related tests
- `@pytest.mark.generation`: Text generation tests

## 📁 Test Structure

```
tests/
├── unit/                          # Unit tests
│   ├── domain/                   # Domain layer tests
│   │   ├── test_document_entities.py
│   │   ├── test_query_entities.py
│   │   └── test_embedding_entities.py
│   ├── application/              # Use case tests
│   │   ├── test_document_use_cases.py
│   │   ├── test_query_use_cases.py
│   │   └── test_generation_use_cases.py
│   └── infrastructure/           # Infrastructure tests
│       ├── test_repositories.py
│       ├── test_model_manager.py
│       └── test_external_apis.py
├── integration/                   # Integration tests
│   ├── api/                     # API integration tests
│   │   ├── test_document_flow.py
│   │   ├── test_query_flow.py
│   │   └── test_auth_flow.py
│   ├── database/                # Database integration tests
│   │   ├── test_postgres_integration.py
│   │   ├── test_redis_integration.py
│   │   └── test_vector_db_integration.py
│   └── messaging/               # Message queue tests
│       ├── test_kafka_integration.py
│       └── test_event_handling.py
├── contract/                     # Contract tests
│   ├── api_contracts/           # API contract tests
│   │   ├── test_document_api_contract.py
│   │   ├── test_query_api_contract.py
│   │   └── test_auth_api_contract.py
│   └── service_contracts/       # Service contract tests
│       ├── test_embedding_service_contract.py
│       ├── test_generation_service_contract.py
│       └── test_model_contract.py
├── e2e/                         # End-to-end tests
│   ├── test_document_lifecycle.py
│   ├── test_query_generation.py
│   └── test_user_workflows.py
├── performance/                  # Performance tests
│   ├── test_load_testing.py
│   ├── test_stress_testing.py
│   └── test_latency_testing.py
├── fixtures/                     # Test data
│   ├── documents/
│   ├── models/
│   └── responses/
├── utils/                       # Test utilities
│   ├── test_helpers.py
│   ├── mock_factories.py
│   └── data_generators.py
├── conftest.py                  # Pytest configuration
├── pytest.ini                  # Pytest settings
└── requirements-test.txt        # Test dependencies
```

## 🔄 CI/CD Pipeline

The testing pipeline is automated through GitHub Actions:

### Pipeline Stages

1. **Unit Tests**: Fast feedback on code changes
2. **Integration Tests**: Verify component interactions
3. **Contract Tests**: Ensure API compatibility
4. **Security Tests**: Scan for vulnerabilities
5. **Code Quality**: Check formatting and linting
6. **Build Test**: Verify Docker builds
7. **Performance Tests**: Load testing (main branch only)
8. **Deploy Staging**: Deploy to staging (develop branch)

### Quality Gates

- **Unit Test Coverage**: Minimum 90%
- **Integration Test Coverage**: Minimum 80%
- **Contract Test Coverage**: 100%
- **Security Scan**: No high-severity issues
- **Code Quality**: All linting checks pass

### Running Pipeline Locally

```bash
# Run the full pipeline locally
docker-compose -f docker-compose.test.yml up -d
pytest tests/ -v --cov=src --cov-report=html
flake8 src/ tests/
black --check src/ tests/
mypy src/
bandit -r src/
```

## 📝 Best Practices

### Writing Tests

1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Use Descriptive Names**: Test method names should describe what they test
3. **Test One Thing**: Each test should verify a single behavior
4. **Use Fixtures**: Leverage pytest fixtures for setup/teardown
5. **Mock External Dependencies**: Use mocks for external services

### Example Test Structure

```python
class TestDocumentUpload:
    """Test document upload functionality"""
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, client, mock_storage):
        """Test successful document upload"""
        # Arrange
        test_file = create_test_file("test content")
        
        # Act
        response = await client.post("/documents/upload", files={"file": test_file})
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "document_id" in data
```

### Test Data Management

1. **Use Factories**: Use factory patterns for test data
2. **Clean Up**: Always clean up test data
3. **Isolate Tests**: Tests should not depend on each other
4. **Use Transactions**: Roll back database changes after tests

### Performance Testing

1. **Set Baselines**: Establish performance baselines
2. **Monitor Resources**: Track CPU, memory, and I/O
3. **Test Realistic Loads**: Simulate realistic user behavior
4. **Profile Bottlenecks**: Identify and optimize slow operations

## 🔧 Troubleshooting

### Common Issues

#### Test Database Connection Issues

```bash
# Check if test database is running
docker-compose -f docker-compose.test.yml ps test-postgres

# Restart database service
docker-compose -f docker-compose.test.yml restart test-postgres

# Check database logs
docker-compose -f docker-compose.test.yml logs test-postgres
```

#### Service Health Check Failures

```bash
# Check all service health
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health

# Restart specific service
docker-compose -f docker-compose.test.yml restart test-document-service
```

#### Timeout Issues

```bash
# Increase timeout for slow tests
pytest tests/integration/ --timeout=600

# Run tests sequentially to avoid resource contention
pytest tests/integration/ -n 1
```

#### Memory Issues

```bash
# Run tests with memory profiling
python -m memory_profiler pytest tests/performance/

# Limit parallel test execution
pytest -n 2
```

### Debugging Tests

```bash
# Run with verbose output
pytest -v -s

# Run with debugger
pytest --pdb

# Run specific test with debugging
pytest tests/unit/domain/test_document_entities.py::TestDocument::test_document_creation --pdb

# Stop on first failure
pytest -x

# Show local variables on failure
pytest --tb=long
```

### Test Coverage Issues

```bash
# Generate detailed coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# Find uncovered lines
coverage report --show-missing

# Generate XML report for CI
coverage xml
```

## 📊 Test Reports

### Viewing Reports

1. **Coverage Report**: Open `htmlcov/index.html`
2. **Performance Report**: Check `benchmark.json`
3. **Test Results**: Check `test-results.xml`
4. **Security Report**: Check `security-reports/`

### Interpreting Results

- **Coverage**: Aim for >90% unit, >80% integration
- **Performance**: Response times should be <2s for queries
- **Security**: No high-severity vulnerabilities
- **Quality**: All linting checks should pass

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r tests/requirements-test.txt

# 2. Start test services
docker-compose -f docker-compose.test.yml up -d

# 3. Run unit tests
pytest tests/unit/ -v

# 4. Run integration tests
pytest tests/integration/ -v

# 5. Run contract tests
pytest tests/contract/ -v

# 6. Check coverage
pytest --cov=src --cov-report=html

# 7. Clean up
docker-compose -f docker-compose.test.yml down -v
```

## 📞 Getting Help

If you encounter issues:

1. Check the [troubleshooting section](#troubleshooting)
2. Review test logs for error messages
3. Ensure all services are running and healthy
4. Verify environment configuration
5. Check GitHub Actions for pipeline issues

For additional support, create an issue in the repository with:
- Error messages
- Test output
- System information
- Steps to reproduce
