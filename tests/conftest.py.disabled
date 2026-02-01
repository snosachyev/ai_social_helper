"""Pytest configuration and fixtures for RAG system tests"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from uuid import uuid4
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.presentation.api.app import create_application
from src.application.use_cases.document_use_case import DocumentUseCase, DocumentUploadResponse
from src.application.use_cases.query_use_case import QueryUseCase, QueryResponse, GenerationResponseData
from src.domain.entities.document import Document, TextChunk, DocumentMetadata, ProcessingStatus, DocumentType
from src.domain.entities.query import QueryRequest, RetrievalResult, GenerationRequest, QueryType
from src.domain.entities.embedding import EmbeddingVector
from src.domain.services.guard_service import Guard, GuardResult
from src.infrastructure.tracing.phoenix_tracer import TracingService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Create FastAPI test application"""
    app = create_application()
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_document_use_case():
    """Mock document use case"""
    mock = Mock(spec=DocumentUseCase)
    
    # Configure async methods
    mock.upload_document = AsyncMock()
    mock.get_document = AsyncMock()
    mock.list_documents = AsyncMock()
    mock.delete_document = AsyncMock()
    mock.update_document_status = AsyncMock()
    
    return mock


@pytest.fixture
def mock_query_use_case():
    """Mock query use case"""
    mock = Mock(spec=QueryUseCase)
    
    # Configure async methods
    mock.execute_query = AsyncMock()
    mock.execute_generation = AsyncMock()
    mock.get_query_suggestions = AsyncMock()
    mock.get_query_history = AsyncMock()
    
    return mock


@pytest.fixture
def mock_tracing_service():
    """Mock tracing service"""
    mock = Mock(spec=TracingService)
    mock.tracer = Mock()
    mock.tracer.trace = Mock()
    mock.tracer.trace.return_value.__aenter__ = AsyncMock(return_value="span_id")
    mock.tracer.trace.return_value.__aexit__ = AsyncMock()
    mock.tracer.add_attribute = AsyncMock()
    mock.trace_query = Mock()
    mock.trace_query.return_value.__aenter__ = AsyncMock()
    mock.trace_query.return_value.__aexit__ = AsyncMock()
    mock.trace_generation = Mock()
    mock.trace_generation.return_value.__aenter__ = AsyncMock()
    mock.trace_generation.return_value.__aexit__ = AsyncMock()
    
    return mock


@pytest.fixture
def mock_container():
    """Mock dependency injection container"""
    container = Mock()
    container.resolve = AsyncMock()
    container.register_singleton = Mock()
    container.cleanup = AsyncMock()
    return container


@pytest.fixture
def app_with_mocks(mock_document_use_case, mock_query_use_case, mock_tracing_service, mock_container):
    """Create FastAPI app with mocked dependencies"""
    from unittest.mock import patch
    from src.presentation.api.document_controller import get_document_use_case as get_doc_use_case
    from src.presentation.api.document_controller import get_tracing_service as get_doc_tracing
    from src.presentation.api.query_controller import get_query_use_case as get_query_use_case_func
    from src.presentation.api.query_controller import get_tracing_service as get_query_tracing
    
    # Create app
    app = create_application()
    
    # Override dependencies
    app.dependency_overrides[get_doc_use_case] = lambda: mock_document_use_case
    app.dependency_overrides[get_doc_tracing] = lambda: mock_tracing_service
    app.dependency_overrides[get_query_use_case_func] = lambda: mock_query_use_case
    app.dependency_overrides[get_query_tracing] = lambda: mock_tracing_service
    
    return app


@pytest.fixture
def sample_document():
    """Create sample document for testing"""
    doc_id = uuid4()
    chunk_id = uuid4()
    
    metadata = DocumentMetadata(
        document_id=doc_id,
        filename="test_document.txt",
        file_type=DocumentType.TXT,
        size_bytes=1000,
        status=ProcessingStatus.COMPLETED,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        metadata={"test": "data"}
    )
    
    chunk = TextChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        text="This is a test chunk of text.",
        chunk_index=0,
        start_char=0,
        end_char=30,
        metadata={"chunk_info": "test"}
    )
    
    document = Document(
        document_id=doc_id,
        metadata=metadata,
        chunks=[chunk]
    )
    
    return document


@pytest.fixture
def sample_document_upload_response():
    """Create sample document upload response"""
    return DocumentUploadResponse(
        document_id=uuid4(),
        filename="test_document.txt",
        status="completed",
        chunk_count=3,
        processing_time_ms=1500,
        metadata={"test": "data"}
    )


@pytest.fixture
def sample_query_request():
    """Create sample query request"""
    return QueryRequest(
        query="What is the meaning of life?",
        query_type=QueryType.SEMANTIC,
        top_k=5,
        filters={"category": "philosophy"},
        metadata={"user_id": "test_user"}
    )


@pytest.fixture
def sample_retrieval_result():
    """Create sample retrieval result"""
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        text="This is relevant text from a document.",
        score=0.85,
        metadata={"source": "test_doc"}
    )


@pytest.fixture
def sample_query_response():
    """Create sample query response"""
    return QueryResponse(
        query_id=uuid4(),
        results=[
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                text="Relevant text 1",
                score=0.9,
                metadata={}
            ),
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                text="Relevant text 2",
                score=0.8,
                metadata={}
            )
        ],
        processing_time_ms=500,
        guard_result=GuardResult(
            is_allowed=True,
            reason="Query is safe",
            risk_score=0.1,
            metadata={}
        ),
        metadata={"test": "data"}
    )


@pytest.fixture
def sample_generation_request():
    """Create sample generation request"""
    return GenerationRequest(
        query="Summarize the following text:",
        context=[
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                text="Context text 1",
                score=0.9,
                metadata={}
            )
        ],
        model_name="gpt-3.5-turbo",
        max_tokens=512,
        temperature=0.7,
        metadata={"user_id": "test_user"}
    )


@pytest.fixture
def sample_generation_response():
    """Create sample generation response"""
    return GenerationResponseData(
        request_id=uuid4(),
        response="This is a generated response based on the context.",
        model_name="gpt-3.5-turbo",
        tokens_used=150,
        processing_time_ms=2000,
        guard_result=GuardResult(
            is_allowed=True,
            reason="Response is safe",
            risk_score=0.05,
            metadata={}
        ),
        metadata={"test": "data"}
    )


@pytest.fixture
def sample_text_file():
    """Create sample text file content"""
    return "This is a test document.\nIt contains multiple lines of text.\nUsed for testing document upload functionality."


@pytest.fixture
def mock_guard_result():
    """Create mock guard result"""
    return GuardResult(
        is_allowed=True,
        reason="Content is safe",
        risk_score=0.1,
        metadata={"category": "safe"}
    )


@pytest.fixture
def dependency_overrides():
    """Dependency overrides for testing"""
    overrides = {}
    return overrides


@pytest.fixture
def mock_container():
    """Mock dependency injection container"""
    container = Mock()
    container.resolve = AsyncMock()
    container.register_singleton = Mock()
    container.cleanup = AsyncMock()
    return container


# Test data fixtures
@pytest.fixture
def invalid_file_content():
    """Invalid file content for testing error cases"""
    return b'\x00\x01\x02\x03\x04'  # Binary content that should fail UTF-8 decoding


@pytest.fixture
def large_file_content():
    """Large file content for testing size limits"""
    return "A" * 10000  # 10KB of text


@pytest.fixture
def sample_filters():
    """Sample filters for testing"""
    return {
        "document_type": "pdf",
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31"
        },
        "tags": ["important", "reviewed"]
    }


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing"""
    return {
        "author": "Test Author",
        "category": "Testing",
        "priority": "high",
        "tags": ["test", "sample"]
    }
