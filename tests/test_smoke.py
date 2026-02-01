"""Smoke tests to verify basic functionality"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from src.presentation.api.app import create_application


class TestBasicFunctionality:
    """Basic smoke tests"""
    
    def test_app_creation(self):
        """Test that app can be created"""
        app = create_application()
        assert app is not None
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        app = create_application()
        client = TestClient(app)
        
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        app = create_application()
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_document_health_endpoint(self):
        """Test document health endpoint"""
        app = create_application()
        client = TestClient(app)
        
        response = client.get("/documents/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "document-service"
    
    def test_query_health_endpoint(self):
        """Test query health endpoint"""
        app = create_application()
        client = TestClient(app)
        
        response = client.get("/query/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "query-service"


class TestDocumentUploadBasic:
    """Basic document upload test with proper mocking"""
    
    def test_document_upload_basic(self):
        """Test document upload with mocked dependencies"""
        # Create mocks
        mock_document_use_case = Mock()
        mock_document_use_case.upload_document = AsyncMock()
        mock_tracing_service = Mock()
        mock_tracing_service.tracer = Mock()
        mock_tracing_service.tracer.trace = Mock()
        mock_tracing_service.tracer.trace.return_value.__aenter__ = AsyncMock(return_value="span_id")
        mock_tracing_service.tracer.trace.return_value.__aexit__ = AsyncMock()
        mock_tracing_service.tracer.add_attribute = AsyncMock()
        
        # Mock response
        from src.application.use_cases.document_use_case import DocumentUploadResponse
        mock_response = DocumentUploadResponse(
            document_id=uuid4(),
            filename="test.txt",
            status="completed",
            chunk_count=3,
            processing_time_ms=1000,
            metadata={}
        )
        mock_document_use_case.upload_document.return_value = mock_response
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.document_controller import get_document_use_case, get_tracing_service
        
        app.dependency_overrides[get_document_use_case] = lambda: mock_document_use_case
        app.dependency_overrides[get_tracing_service] = lambda: mock_tracing_service
        
        # Create client and test
        client = TestClient(app)
        
        response = client.post(
            "/documents/upload",
            files={"file": ("test.txt", "This is test content", "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(mock_response.document_id)
        assert data["filename"] == mock_response.filename
        assert data["status"] == mock_response.status
        
        # Verify mock was called
        mock_document_use_case.upload_document.assert_called_once()


class TestQueryBasic:
    """Basic query test with proper mocking"""
    
    def test_query_basic(self):
        """Test query processing with mocked dependencies"""
        # Create mocks
        mock_query_use_case = Mock()
        mock_query_use_case.execute_query = AsyncMock()
        mock_tracing_service = Mock()
        mock_tracing_service.trace_query = Mock()
        mock_tracing_service.trace_query.return_value.__aenter__ = AsyncMock()
        mock_tracing_service.trace_query.return_value.__aexit__ = AsyncMock()
        
        # Mock response
        from src.application.use_cases.query_use_case import QueryResponse
        from src.domain.services.guard_service import GuardResult
        from src.domain.entities.embedding import RetrievalResult
        
        mock_response = QueryResponse(
            query_id=uuid4(),
            results=[
                RetrievalResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    text="Test result",
                    score=0.9,
                    metadata={}
                )
            ],
            processing_time_ms=500,
            guard_result=GuardResult(
                is_allowed=True,
                reason="Safe",
                risk_score=0.1,
                metadata={}
            ),
            metadata={}
        )
        mock_query_use_case.execute_query.return_value = mock_response
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.query_controller import get_query_use_case, get_tracing_service
        
        app.dependency_overrides[get_query_use_case] = lambda: mock_query_use_case
        app.dependency_overrides[get_tracing_service] = lambda: mock_tracing_service
        
        # Create client and test
        client = TestClient(app)
        
        query_data = {
            "query": "What is AI?",
            "query_type": "semantic",
            "top_k": 5
        }
        
        response = client.post("/query/", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["query_id"] == str(mock_response.query_id)
        assert len(data["results"]) == 1
        assert data["results"][0]["text"] == "Test result"
        assert data["guard_result"]["is_allowed"] is True
        
        # Verify mock was called
        mock_query_use_case.execute_query.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
