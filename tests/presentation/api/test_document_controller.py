"""Tests for document controller endpoints"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json

from src.domain.entities.document import ProcessingStatus, DocumentType
from src.application.services.dependency_injection import get_container


class TestDocumentUpload:
    """Test document upload endpoint"""
    
    def test_upload_document_success(self, app_with_mocks, mock_document_use_case, mock_tracing_service, sample_document_upload_response, sample_text_file):
        """Test successful document upload"""
        # Setup mock
        mock_document_use_case.upload_document.return_value = sample_document_upload_response
        
        # Create test client with mocked app
        client = TestClient(app_with_mocks)
        
        # Make request
        response = client.post(
            "/documents/upload",
            files={"file": ("test.txt", sample_text_file, "text/plain")}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(sample_document_upload_response.document_id)
        assert data["filename"] == sample_document_upload_response.filename
        assert data["status"] == sample_document_upload_response.status
        assert data["chunk_count"] == sample_document_upload_response.chunk_count
        assert data["processing_time_ms"] == sample_document_upload_response.processing_time_ms
        
        # Verify mock calls
        mock_document_use_case.upload_document.assert_called_once()
    
    def test_upload_document_without_filename(self, app_with_mocks, mock_document_use_case, mock_tracing_service, sample_document_upload_response):
        """Test document upload without filename"""
        # Setup mock
        mock_document_use_case.upload_document.return_value = sample_document_upload_response
        
        # Create test client with mocked app
        client = TestClient(app_with_mocks)
        
        # Make request without filename
        response = client.post(
            "/documents/upload",
            files={"file": (None, "test content", "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "unknown"  # Should default to "unknown"
    
    def test_upload_document_invalid_file_type(self, client, mock_document_use_case, mock_tracing_service, sample_document_upload_response):
        """Test document upload with unsupported file type defaults to TXT"""
        mock_document_use_case.upload_document.return_value = sample_document_upload_response
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                # Make request with unsupported file type
                response = client.post(
                    "/documents/upload",
                    files={"file": ("test.xyz", "test content", "text/plain")}
                )
        
        assert response.status_code == 200
        # Should default to TXT type
        call_args = mock_document_use_case.upload_document.call_args
        assert call_args[1]['file_type'] == DocumentType.TXT
    
    def test_upload_document_encoding_error(self, client, mock_tracing_service, invalid_file_content):
        """Test document upload with invalid encoding"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                # Make request with binary content
                response = client.post(
                    "/documents/upload",
                    files={"file": ("test.bin", invalid_file_content, "application/octet-stream")}
                )
        
        assert response.status_code == 400
        data = response.json()
        assert "File encoding not supported" in data["detail"]
    
    def test_upload_document_use_case_exception(self, client, mock_document_use_case, mock_tracing_service, sample_text_file):
        """Test document upload when use case raises exception"""
        # Setup mock to raise exception
        mock_document_use_case.upload_document.side_effect = Exception("Processing failed")
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.post(
                    "/documents/upload",
                    files={"file": ("test.txt", sample_text_file, "text/plain")}
                )
        
        assert response.status_code == 500
        data = response.json()
        assert "Document upload failed" in data["detail"]


class TestGetDocument:
    """Test get document endpoint"""
    
    def test_get_document_success(self, client, mock_document_use_case, mock_tracing_service, sample_document):
        """Test successful document retrieval"""
        mock_document_use_case.get_document.return_value = sample_document
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get(f"/documents/{sample_document.document_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(sample_document.document_id)
        assert data["metadata"]["filename"] == sample_document.metadata.filename
        assert data["metadata"]["file_type"] == sample_document.metadata.file_type.value
        assert data["metadata"]["status"] == sample_document.metadata.status.value
        assert len(data["chunks"]) == len(sample_document.chunks)
        assert data["chunk_count"] == len(sample_document.chunks)
    
    def test_get_document_not_found(self, client, mock_document_use_case, mock_tracing_service):
        """Test get document when document not found"""
        mock_document_use_case.get_document.return_value = None
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                response = client.get(f"/documents/{doc_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "Document not found" in data["detail"]
    
    def test_get_document_invalid_uuid(self, client, mock_tracing_service):
        """Test get document with invalid UUID"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/invalid-uuid")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid document ID format" in data["detail"]
    
    def test_get_document_use_case_exception(self, client, mock_document_use_case, mock_tracing_service):
        """Test get document when use case raises exception"""
        mock_document_use_case.get_document.side_effect = Exception("Database error")
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                response = client.get(f"/documents/{doc_id}")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get document" in data["detail"]


class TestListDocuments:
    """Test list documents endpoint"""
    
    def test_list_documents_success(self, client, mock_document_use_case, mock_tracing_service, sample_document):
        """Test successful document listing"""
        mock_document_use_case.list_documents.return_value = [sample_document]
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/")
        
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "count" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["documents"]) == 1
        assert data["count"] == 1
        assert data["skip"] == 0
        assert data["limit"] == 100
        
        # Verify document data
        doc_data = data["documents"][0]
        assert doc_data["document_id"] == str(sample_document.document_id)
        assert doc_data["filename"] == sample_document.metadata.filename
        assert doc_data["file_type"] == sample_document.metadata.file_type.value
    
    def test_list_documents_with_pagination(self, client, mock_document_use_case, mock_tracing_service, sample_document):
        """Test document listing with pagination"""
        mock_document_use_case.list_documents.return_value = [sample_document]
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/?skip=10&limit=20")
        
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 10
        assert data["limit"] == 20
        
        # Verify use case was called with correct parameters
        mock_document_use_case.list_documents.assert_called_once_with(10, 20, None)
    
    def test_list_documents_with_status_filter(self, client, mock_document_use_case, mock_tracing_service, sample_document):
        """Test document listing with status filter"""
        mock_document_use_case.list_documents.return_value = [sample_document]
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/?status=completed")
        
        assert response.status_code == 200
        
        # Verify use case was called with correct status
        mock_document_use_case.list_documents.assert_called_once_with(0, 100, ProcessingStatus.COMPLETED)
    
    def test_list_documents_invalid_status(self, client, mock_tracing_service):
        """Test document listing with invalid status"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/?status=invalid_status")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid status" in data["detail"]
    
    def test_list_documents_use_case_exception(self, client, mock_document_use_case, mock_tracing_service):
        """Test document listing when use case raises exception"""
        mock_document_use_case.list_documents.side_effect = Exception("Database error")
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.get("/documents/")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to list documents" in data["detail"]


class TestDeleteDocument:
    """Test delete document endpoint"""
    
    def test_delete_document_success(self, client, mock_document_use_case, mock_tracing_service):
        """Test successful document deletion"""
        mock_document_use_case.delete_document.return_value = True
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                response = client.delete(f"/documents/{doc_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(doc_id)
        assert data["deleted"] is True
        assert "deleted successfully" in data["message"]
    
    def test_delete_document_not_found(self, client, mock_document_use_case, mock_tracing_service):
        """Test delete document when document not found"""
        mock_document_use_case.delete_document.return_value = False
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                response = client.delete(f"/documents/{doc_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "Document not found" in data["detail"]
    
    def test_delete_document_invalid_uuid(self, client, mock_tracing_service):
        """Test delete document with invalid UUID"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                response = client.delete("/documents/invalid-uuid")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid document ID format" in data["detail"]
    
    def test_delete_document_use_case_exception(self, client, mock_document_use_case, mock_tracing_service):
        """Test delete document when use case raises exception"""
        mock_document_use_case.delete_document.side_effect = Exception("Database error")
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                response = client.delete(f"/documents/{doc_id}")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to delete document" in data["detail"]


class TestUpdateDocumentStatus:
    """Test update document status endpoint"""
    
    def test_update_document_status_success(self, client, mock_document_use_case, mock_tracing_service):
        """Test successful document status update"""
        mock_document_use_case.update_document_status.return_value = True
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                status_data = {"status": "completed"}
                response = client.patch(
                    f"/documents/{doc_id}/status",
                    json=status_data
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(doc_id)
        assert data["status"] == "completed"
        assert data["updated"] is True
        assert "updated successfully" in data["message"]
    
    def test_update_document_status_not_found(self, client, mock_document_use_case, mock_tracing_service):
        """Test update document status when document not found"""
        mock_document_use_case.update_document_status.return_value = False
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                status_data = {"status": "completed"}
                response = client.patch(
                    f"/documents/{doc_id}/status",
                    json=status_data
                )
        
        assert response.status_code == 404
        data = response.json()
        assert "Document not found" in data["detail"]
    
    def test_update_document_status_invalid_uuid(self, client, mock_tracing_service):
        """Test update document status with invalid UUID"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                status_data = {"status": "completed"}
                response = client.patch(
                    "/documents/invalid-uuid/status",
                    json=status_data
                )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid document ID format" in data["detail"]
    
    def test_update_document_status_invalid_status(self, client, mock_tracing_service):
        """Test update document status with invalid status"""
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = AsyncMock()
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                status_data = {"status": "invalid_status"}
                response = client.patch(
                    f"/documents/{doc_id}/status",
                    json=status_data
                )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid input" in data["detail"]
    
    def test_update_document_status_default_pending(self, client, mock_document_use_case, mock_tracing_service):
        """Test update document status with no status provided (defaults to pending)"""
        mock_document_use_case.update_document_status.return_value = True
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                doc_id = uuid4()
                status_data = {}  # No status provided
                response = client.patch(
                    f"/documents/{doc_id}/status",
                    json=status_data
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"  # Should default to pending


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/documents/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "document-service"
        assert data["version"] == "1.0.0"


class TestAsyncDocumentUpload:
    """Test async document upload with httpx client"""
    
    @pytest.mark.asyncio
    async def test_async_upload_document_success(self, async_client, mock_document_use_case, mock_tracing_service, sample_document_upload_response):
        """Test successful async document upload"""
        mock_document_use_case.upload_document.return_value = sample_document_upload_response
        
        with patch('src.presentation.api.document_controller.get_document_use_case') as mock_get_doc:
            with patch('src.presentation.api.document_controller.get_tracing_service') as mock_get_trace:
                mock_get_doc.return_value = mock_document_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                files = {"file": ("test.txt", "test content", "text/plain")}
                response = await async_client.post("/documents/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == str(sample_document_upload_response.document_id)
        assert data["filename"] == sample_document_upload_response.filename
