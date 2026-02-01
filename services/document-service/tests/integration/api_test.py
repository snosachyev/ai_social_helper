import pytest
from fastapi.testclient import TestClient
from io import BytesIO

from main import app


class TestDocumentAPIIntegration:
    """Integration tests for Document API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        with TestClient(app) as test_client:
            yield test_client
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "document-service"
    
    def test_upload_document_invalid_type(self, client):
        """Test upload with invalid file type."""
        content = b"fake content"
        
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.xyz", BytesIO(content), "application/octet-stream")}
        )
        
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    
    def test_get_document_not_found(self, client):
        """Test getting non-existent document."""
        response = client.get("/api/v1/documents/non-existent-id")
        
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]
    
    def test_list_documents_empty(self, client):
        """Test listing documents when none exist."""
        response = client.get("/api/v1/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_document_chunks_not_found(self, client):
        """Test getting chunks for non-existent document."""
        response = client.get("/api/v1/documents/non-existent-id/chunks")
        
        assert response.status_code == 404
        assert "Document chunks not found" in response.json()["detail"]


class TestDocumentProcessorIntegration:
    """Integration tests for document processor components."""
    
    def test_file_validator_supported_types(self):
        """Test file validator with supported types."""
        from src.infrastructure.external.document_processor_impl import FileValidatorImpl
        
        validator = FileValidatorImpl()
        
        assert validator.validate_file_type("test.pdf") is True
        assert validator.validate_file_type("test.txt") is True
        assert validator.validate_file_type("test.docx") is True
        assert validator.validate_file_type("test.html") is True
        assert validator.validate_file_type("test.md") is True
    
    def test_file_validator_unsupported_types(self):
        """Test file validator with unsupported types."""
        from src.infrastructure.external.document_processor_impl import FileValidatorImpl
        
        validator = FileValidatorImpl()
        
        assert validator.validate_file_type("test.xyz") is False
        assert validator.validate_file_type("test.exe") is False
    
    def test_text_chunker_small_text(self):
        """Test text chunker with small text."""
        from src.infrastructure.external.document_processor_impl import TextChunkerImpl
        
        chunker = TextChunkerImpl()
        text = "This is a small text."
        
        chunks = chunker.chunk_text(text, chunk_size=1000, overlap=200)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_text_chunker_large_text(self):
        """Test text chunker with large text."""
        from src.infrastructure.external.document_processor_impl import TextChunkerImpl
        
        chunker = TextChunkerImpl()
        text = "This is sentence one. This is sentence two. This is sentence three. " * 100
        
        chunks = chunker.chunk_text(text, chunk_size=200, overlap=50)
        
        assert len(chunks) > 1
        # Verify chunks are not empty
        for chunk in chunks:
            assert len(chunk.strip()) > 0
