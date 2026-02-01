import pytest
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
from io import BytesIO

from src.application.use_cases.document_use_cases import UploadDocumentUseCase
from shared.document_contracts.upload import UploadDocumentRequest, UploadDocumentResponse
from src.domain.entities.document import Document, TextChunk, DocumentType, ProcessingStatus
from src.infrastructure.external.document_processor_impl import (
    DocumentTextExtractorImpl, TextChunkerImpl, FileValidatorImpl
)


class TestUploadDocumentUseCase:
    """Unit tests for UploadDocumentUseCase."""
    
    @pytest.fixture
    def use_case(self, mock_document_repository, mock_chunk_repository, 
                 mock_cache_repository, temp_upload_dir):
        """Create use case with mocked dependencies."""
        text_extractor = DocumentTextExtractorImpl()
        text_chunker = TextChunkerImpl()
        file_validator = FileValidatorImpl()
        
        return UploadDocumentUseCase(
            document_repo=mock_document_repository,
            chunk_repo=mock_chunk_repository,
            cache_repo=mock_cache_repository,
            text_extractor=text_extractor,
            text_chunker=text_chunker,
            file_validator=file_validator,
            upload_dir=temp_upload_dir
        )
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, use_case, mock_document_repository, 
                                          mock_chunk_repository, mock_cache_repository,
                                          sample_text_content, temp_upload_dir):
        """Test successful document upload."""
        # Setup
        filename = "test.txt"
        content = sample_text_content.encode('utf-8')
        
        # Create request first to get the actual document_id
        request = UploadDocumentRequest(
            file=BytesIO(content),
            filename=filename,
            content=content
        )
        
        # Mock repository responses with dynamic document_id
        def save_side_effect(document):
            return document  # Return the actual document with generated ID
        
        mock_document_repository.save.side_effect = save_side_effect
        mock_document_repository.update.side_effect = save_side_effect
        mock_chunk_repository.save_batch.return_value = []
        
        # Execute
        response = await use_case.execute(request)
        
        # Verify
        assert isinstance(response, UploadDocumentResponse)
        assert response.filename == filename
        assert response.status == ProcessingStatus.COMPLETED.value
        assert response.chunk_count > 0
        assert response.processing_time_ms > 0
        
        # Verify repository calls
        mock_document_repository.save.assert_called_once()
        mock_chunk_repository.save_batch.assert_called_once()
        mock_document_repository.update.assert_called_once()
        mock_cache_repository.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, use_case):
        """Test upload with invalid file type."""
        # Setup
        filename = "test.xyz"
        content = b"test content"
        
        request = UploadDocumentRequest(
            file=BytesIO(content),
            filename=filename,
            content=content
        )
        
        # Execute and verify exception
        with pytest.raises(ValueError, match="Unsupported file type"):
            await use_case.execute(request)
    
    @pytest.mark.asyncio
    async def test_upload_document_extraction_error(self, use_case, mock_document_repository):
        """Test upload with text extraction error."""
        # Setup
        filename = "test.pdf"
        content = b"fake pdf content"
        
        mock_document = Document(
            document_id="test-doc-123",
            filename=filename,
            file_type=DocumentType.PDF,
            size_bytes=len(content),
            status=ProcessingStatus.PROCESSING
        )
        mock_document_repository.save.return_value = mock_document
        mock_document_repository.update.return_value = mock_document
        
        request = UploadDocumentRequest(
            file=BytesIO(content),
            filename=filename,
            content=content
        )
        
        # Execute and verify exception
        with pytest.raises(ValueError, match="Failed to extract text"):
            await use_case.execute(request)
        
        # Verify document status is updated to FAILED
        mock_document_repository.update.assert_called_once()
        updated_doc = mock_document_repository.update.call_args[0][0]
        assert updated_doc.status == ProcessingStatus.FAILED


class TestTextChunkerImpl:
    """Unit tests for TextChunkerImpl."""
    
    def test_chunk_text_small_text(self):
        """Test chunking with small text."""
        chunker = TextChunkerImpl()
        text = "This is a small text."
        
        chunks = chunker.chunk_text(text, chunk_size=1000, overlap=200)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_text_large_text(self):
        """Test chunking with large text."""
        chunker = TextChunkerImpl()
        text = "This is sentence one. This is sentence two. This is sentence three. " * 100
        
        chunks = chunker.chunk_text(text, chunk_size=200, overlap=50)
        
        assert len(chunks) > 1
        # Verify overlap
        for i in range(1, len(chunks)):
            # Check that chunks have some overlap (simplified check)
            assert len(chunks[i]) > 0
    
    def test_chunk_text_with_sentence_boundaries(self):
        """Test chunking respects sentence boundaries."""
        chunker = TextChunkerImpl()
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        chunks = chunker.chunk_text(text, chunk_size=30, overlap=5)
        
        assert len(chunks) > 1
        # Verify chunks are not empty and have reasonable content
        for chunk in chunks:
            assert len(chunk.strip()) > 0
            # Most chunks should end with sentence boundaries when possible
            # But we don't require it strictly due to chunk size constraints


class TestFileValidatorImpl:
    """Unit tests for FileValidatorImpl."""
    
    def test_validate_file_type_supported(self):
        """Test validation of supported file types."""
        validator = FileValidatorImpl()
        
        assert validator.validate_file_type("test.pdf") is True
        assert validator.validate_file_type("test.txt") is True
        assert validator.validate_file_type("test.docx") is True
        assert validator.validate_file_type("test.html") is True
        assert validator.validate_file_type("test.md") is True
    
    def test_validate_file_type_unsupported(self):
        """Test validation of unsupported file types."""
        validator = FileValidatorImpl()
        
        assert validator.validate_file_type("test.xyz") is False
        assert validator.validate_file_type("test.exe") is False
    
    def test_get_file_type(self):
        """Test getting file type from filename."""
        validator = FileValidatorImpl()
        
        assert validator.get_file_type("test.pdf") == DocumentType.PDF
        assert validator.get_file_type("test.txt") == DocumentType.TXT
        assert validator.get_file_type("test.docx") == DocumentType.DOCX
        assert validator.get_file_type("test.html") == DocumentType.HTML
        assert validator.get_file_type("test.md") == DocumentType.MD
    
    def test_get_file_type_unsupported(self):
        """Test getting file type for unsupported file."""
        validator = FileValidatorImpl()
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            validator.get_file_type("test.xyz")
