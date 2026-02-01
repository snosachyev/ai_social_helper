"""Unit tests for document use cases"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open
from uuid import uuid4
from datetime import datetime
import tempfile
import os

from services.document_service.src.application.use_cases.document_use_cases import (
    UploadDocumentUseCase, GetDocumentUseCase, ListDocumentsUseCase,
    UploadDocumentRequest, GetDocumentRequest, ListDocumentsRequest
)
from services.document_service.src.domain.entities.document import (
    Document, TextChunk, ProcessingResult, DocumentType, ProcessingStatus
)
from services.document_service.src.domain.repositories.document_repository import DocumentRepository
from services.document_service.src.domain.services.document_processor import DocumentProcessor


class TestUploadDocumentUseCase:
    """Test UploadDocumentUseCase"""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock document repository"""
        return Mock(spec=DocumentRepository)
    
    @pytest.fixture
    def mock_processor(self):
        """Mock document processor"""
        return Mock(spec=DocumentProcessor)
    
    @pytest.fixture
    def upload_use_case(self, mock_repository, mock_processor):
        """Upload document use case with mocked dependencies"""
        return UploadDocumentUseCase(mock_repository, mock_processor)
    
    @pytest.fixture
    def sample_file_content(self):
        """Sample file content for testing"""
        return b"This is a test document content.\nIt has multiple lines.\nUsed for testing document upload."
    
    @pytest.fixture
    def upload_request(self, sample_file_content):
        """Sample upload request"""
        return UploadDocumentRequest(
            file=mock_open(read_data=sample_file_content.decode()).return_value,
            filename="test_document.txt",
            content=sample_file_content
        )
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, upload_use_case, mock_repository, mock_processor, upload_request):
        """Test successful document upload"""
        # Arrange
        doc_id = str(uuid4())
        chunks = [
            TextChunk(
                chunk_id=str(uuid4()),
                document_id=doc_id,
                text="This is a test document content.",
                chunk_index=0,
                start_char=0,
                end_char=35
            ),
            TextChunk(
                chunk_id=str(uuid4()),
                document_id=doc_id,
                text="It has multiple lines.",
                chunk_index=1,
                start_char=36,
                end_char=60
            )
        ]
        
        expected_result = ProcessingResult(
            document=Document(
                document_id=doc_id,
                filename="test_document.txt",
                file_type=DocumentType.TXT,
                size_bytes=len(upload_request.content),
                status=ProcessingStatus.COMPLETED
            ),
            chunks=chunks,
            processing_time_ms=1500
        )
        
        mock_processor.process_document.return_value = expected_result
        mock_repository.save_document.return_value = expected_result.document
        mock_repository.save_chunks.return_value = chunks
        
        # Act
        result = await upload_use_case.execute(upload_request)
        
        # Assert
        assert result is not None
        assert result.document.document_id == doc_id
        assert result.document.filename == "test_document.txt"
        assert result.document.file_type == DocumentType.TXT
        assert result.document.status == ProcessingStatus.COMPLETED
        assert len(result.chunks) == 2
        assert result.processing_time_ms == 1500
        assert result.is_successful is True
        
        # Verify interactions
        mock_processor.process_document.assert_called_once()
        mock_repository.save_document.assert_called_once_with(expected_result.document)
        mock_repository.save_chunks.assert_called_once_with(chunks)
    
    @pytest.mark.asyncio
    async def test_upload_document_processing_failure(self, upload_use_case, mock_processor, upload_request):
        """Test document upload with processing failure"""
        # Arrange
        error_result = ProcessingResult(
            document=Document(
                filename="test_document.txt",
                file_type=DocumentType.TXT,
                status=ProcessingStatus.FAILED
            ),
            chunks=[],
            processing_time_ms=500,
            errors=["Unsupported file format", "Corrupted content"]
        )
        
        mock_processor.process_document.return_value = error_result
        
        # Act
        result = await upload_use_case.execute(upload_request)
        
        # Assert
        assert result is not None
        assert result.document.status == ProcessingStatus.FAILED
        assert result.is_successful is False
        assert len(result.errors) == 2
        assert "Unsupported file format" in result.errors
        assert "Corrupted content" in result.errors
    
    @pytest.mark.asyncio
    async def test_upload_document_repository_error(self, upload_use_case, mock_repository, mock_processor, upload_request):
        """Test document upload with repository error"""
        # Arrange
        doc_id = str(uuid4())
        expected_result = ProcessingResult(
            document=Document(document_id=doc_id, filename="test_document.txt"),
            chunks=[],
            processing_time_ms=1000
        )
        
        mock_processor.process_document.return_value = expected_result
        mock_repository.save_document.side_effect = Exception("Database connection failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Database connection failed"):
            await upload_use_case.execute(upload_request)
    
    @pytest.mark.asyncio
    async def test_upload_document_different_file_types(self, upload_use_case, mock_processor, mock_repository):
        """Test upload documents with different file types"""
        # Test PDF
        pdf_request = UploadDocumentRequest(
            file=mock_open(read_data="fake pdf content").return_value,
            filename="document.pdf",
            content=b"fake pdf content"
        )
        
        pdf_result = ProcessingResult(
            document=Document(
                filename="document.pdf",
                file_type=DocumentType.PDF,
                size_bytes=17
            ),
            chunks=[],
            processing_time_ms=2000
        )
        
        mock_processor.process_document.return_value = pdf_result
        mock_repository.save_document.return_value = pdf_result.document
        
        result = await upload_use_case.execute(pdf_request)
        assert result.document.file_type == DocumentType.PDF
        
        # Test DOCX
        docx_request = UploadDocumentRequest(
            file=mock_open(read_data="fake docx content").return_value,
            filename="document.docx",
            content=b"fake docx content"
        )
        
        docx_result = ProcessingResult(
            document=Document(
                filename="document.docx",
                file_type=DocumentType.DOCX,
                size_bytes=18
            ),
            chunks=[],
            processing_time_ms=2500
        )
        
        mock_processor.process_document.return_value = docx_result
        mock_repository.save_document.return_value = docx_result.document
        
        result = await upload_use_case.execute(docx_request)
        assert result.document.file_type == DocumentType.DOCX


class TestGetDocumentUseCase:
    """Test GetDocumentUseCase"""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock document repository"""
        return Mock(spec=DocumentRepository)
    
    @pytest.fixture
    def get_use_case(self, mock_repository):
        """Get document use case with mocked repository"""
        return GetDocumentUseCase(mock_repository)
    
    @pytest.fixture
    def sample_document(self):
        """Sample document for testing"""
        return Document(
            document_id=str(uuid4()),
            filename="sample.pdf",
            file_type=DocumentType.PDF,
            size_bytes=1024,
            status=ProcessingStatus.COMPLETED,
            metadata={"author": "Test Author", "category": "Testing"}
        )
    
    @pytest.mark.asyncio
    async def test_get_document_success(self, get_use_case, mock_repository, sample_document):
        """Test successful document retrieval"""
        # Arrange
        request = GetDocumentRequest(document_id=sample_document.document_id)
        mock_repository.get_document.return_value = sample_document
        
        # Act
        result = await get_use_case.execute(request)
        
        # Assert
        assert result is not None
        assert result.document == sample_document
        assert result.document.document_id == sample_document.document_id
        assert result.document.filename == "sample.pdf"
        assert result.document.file_type == DocumentType.PDF
        
        mock_repository.get_document.assert_called_once_with(sample_document.document_id)
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, get_use_case, mock_repository):
        """Test document retrieval when document not found"""
        # Arrange
        doc_id = str(uuid4())
        request = GetDocumentRequest(document_id=doc_id)
        mock_repository.get_document.return_value = None
        
        # Act
        result = await get_use_case.execute(request)
        
        # Assert
        assert result is not None
        assert result.document is None
        
        mock_repository.get_document.assert_called_once_with(doc_id)
    
    @pytest.mark.asyncio
    async def test_get_document_repository_error(self, get_use_case, mock_repository):
        """Test document retrieval with repository error"""
        # Arrange
        doc_id = str(uuid4())
        request = GetDocumentRequest(document_id=doc_id)
        mock_repository.get_document.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await get_use_case.execute(request)


class TestListDocumentsUseCase:
    """Test ListDocumentsUseCase"""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock document repository"""
        return Mock(spec=DocumentRepository)
    
    @pytest.fixture
    def list_use_case(self, mock_repository):
        """List documents use case with mocked repository"""
        return ListDocumentsUseCase(mock_repository)
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents list for testing"""
        return [
            Document(
                document_id=str(uuid4()),
                filename="doc1.pdf",
                file_type=DocumentType.PDF,
                size_bytes=1024,
                status=ProcessingStatus.COMPLETED
            ),
            Document(
                document_id=str(uuid4()),
                filename="doc2.txt",
                file_type=DocumentType.TXT,
                size_bytes=512,
                status=ProcessingStatus.PROCESSING
            ),
            Document(
                document_id=str(uuid4()),
                filename="doc3.docx",
                file_type=DocumentType.DOCX,
                size_bytes=2048,
                status=ProcessingStatus.COMPLETED
            )
        ]
    
    @pytest.mark.asyncio
    async def test_list_documents_success(self, list_use_case, mock_repository, sample_documents):
        """Test successful documents listing"""
        # Arrange
        request = ListDocumentsRequest(skip=0, limit=10)
        mock_repository.list_documents.return_value = sample_documents
        
        # Act
        result = await list_use_case.execute(request)
        
        # Assert
        assert result is not None
        assert len(result.documents) == 3
        assert result.documents[0].filename == "doc1.pdf"
        assert result.documents[1].filename == "doc2.txt"
        assert result.documents[2].filename == "doc3.docx"
        
        mock_repository.list_documents.assert_called_once_with(skip=0, limit=10)
    
    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(self, list_use_case, mock_repository, sample_documents):
        """Test documents listing with pagination"""
        # Arrange
        request = ListDocumentsRequest(skip=1, limit=2)
        mock_repository.list_documents.return_value = sample_documents[1:3]
        
        # Act
        result = await list_use_case.execute(request)
        
        # Assert
        assert len(result.documents) == 2
        assert result.documents[0].filename == "doc2.txt"
        assert result.documents[1].filename == "doc3.docx"
        
        mock_repository.list_documents.assert_called_once_with(skip=1, limit=2)
    
    @pytest.mark.asyncio
    async def test_list_documents_empty_result(self, list_use_case, mock_repository):
        """Test documents listing with empty result"""
        # Arrange
        request = ListDocumentsRequest(skip=0, limit=10)
        mock_repository.list_documents.return_value = []
        
        # Act
        result = await list_use_case.execute(request)
        
        # Assert
        assert result is not None
        assert len(result.documents) == 0
        
        mock_repository.list_documents.assert_called_once_with(skip=0, limit=10)
    
    @pytest.mark.asyncio
    async def test_list_documents_repository_error(self, list_use_case, mock_repository):
        """Test documents listing with repository error"""
        # Arrange
        request = ListDocumentsRequest(skip=0, limit=10)
        mock_repository.list_documents.side_effect = Exception("Connection failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Connection failed"):
            await list_use_case.execute(request)
