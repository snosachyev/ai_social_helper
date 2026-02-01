import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

from src.domain.entities.document import Document, DocumentType, ProcessingStatus
from src.domain.repositories.document_repository import DocumentRepository, ChunkRepository, CacheRepository


@pytest.fixture
def temp_upload_dir():
    """Create temporary upload directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_document_repository():
    """Mock document repository."""
    repo = Mock(spec=DocumentRepository)
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_all = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_chunk_repository():
    """Mock chunk repository."""
    repo = Mock(spec=ChunkRepository)
    repo.save = AsyncMock()
    repo.save_batch = AsyncMock()
    repo.get_by_document_id = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.delete_by_document_id = AsyncMock()
    return repo


@pytest.fixture
def mock_cache_repository():
    """Mock cache repository."""
    repo = Mock(spec=CacheRepository)
    repo.get = AsyncMock()
    repo.set = AsyncMock()
    repo.delete = AsyncMock()
    repo.exists = AsyncMock()
    return repo


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return Document(
        document_id="test-doc-123",
        filename="test.pdf",
        file_type=DocumentType.PDF,
        size_bytes=1024,
        status=ProcessingStatus.PENDING
    )


@pytest.fixture
def sample_text_content():
    """Sample text content for testing."""
    return """
    This is a sample document for testing purposes.
    It contains multiple sentences to test text chunking.
    The text should be split into meaningful chunks.
    Each chunk should contain complete sentences when possible.
    This ensures better context preservation for downstream processing.
    """


@pytest.fixture
def test_app():
    """Test FastAPI application."""
    from main import app
    return TestClient(app)
