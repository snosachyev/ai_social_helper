"""Unit tests for document domain entities"""

import pytest
from datetime import datetime
from uuid import uuid4
import sys
import os

# Add the service path to Python path
service_path = os.path.join(os.path.dirname(__file__), '../../../../services/document-service/src')
sys.path.insert(0, service_path)

# Import directly from the module
from domain.entities.document import (
    Document, TextChunk, ProcessingResult, DocumentType, ProcessingStatus
)


class TestDocument:
    """Test Document entity"""
    
    def test_document_creation_with_defaults(self):
        """Test document creation with default values"""
        doc = Document()
        
        assert doc.document_id is not None
        assert doc.filename == ""
        assert doc.file_type == DocumentType.TXT
        assert doc.size_bytes == 0
        assert doc.status == ProcessingStatus.PENDING
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
        assert doc.metadata == {}
    
    def test_document_creation_with_values(self):
        """Test document creation with specific values"""
        doc_id = str(uuid4())
        created_at = datetime.utcnow()
        
        doc = Document(
            document_id=doc_id,
            filename="test.pdf",
            file_type=DocumentType.PDF,
            size_bytes=1024,
            status=ProcessingStatus.COMPLETED,
            created_at=created_at,
            metadata={"author": "test"}
        )
        
        assert doc.document_id == doc_id
        assert doc.filename == "test.pdf"
        assert doc.file_type == DocumentType.PDF
        assert doc.size_bytes == 1024
        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.created_at == created_at
        assert doc.metadata == {"author": "test"}
    
    def test_update_status(self):
        """Test status update functionality"""
        doc = Document()
        original_updated_at = doc.updated_at
        
        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        doc.update_status(ProcessingStatus.PROCESSING)
        
        assert doc.status == ProcessingStatus.PROCESSING
        assert doc.updated_at > original_updated_at
    
    def test_add_metadata(self):
        """Test metadata addition"""
        doc = Document()
        original_updated_at = doc.updated_at
        
        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        doc.add_metadata("author", "Test Author")
        doc.add_metadata("category", "Testing")
        
        assert doc.metadata == {"author": "Test Author", "category": "Testing"}
        assert doc.updated_at > original_updated_at
    
    def test_add_metadata_overwrite(self):
        """Test metadata overwrite functionality"""
        doc = Document()
        doc.add_metadata("author", "Original Author")
        doc.add_metadata("author", "New Author")
        
        assert doc.metadata == {"author": "New Author"}


class TestTextChunk:
    """Test TextChunk entity"""
    
    def test_chunk_creation_with_defaults(self):
        """Test chunk creation with default values"""
        chunk = TextChunk()
        
        assert chunk.chunk_id is not None
        assert chunk.document_id == ""
        assert chunk.text == ""
        assert chunk.chunk_index == 0
        assert chunk.start_char == 0
        assert chunk.end_char == 0
        assert chunk.metadata == {}
    
    def test_chunk_creation_with_values(self):
        """Test chunk creation with specific values"""
        chunk_id = str(uuid4())
        document_id = str(uuid4())
        
        chunk = TextChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            text="This is a test chunk",
            chunk_index=1,
            start_char=10,
            end_char=30,
            metadata={"page": 1}
        )
        
        assert chunk.chunk_id == chunk_id
        assert chunk.document_id == document_id
        assert chunk.text == "This is a test chunk"
        assert chunk.chunk_index == 1
        assert chunk.start_char == 10
        assert chunk.end_char == 30
        assert chunk.metadata == {"page": 1}
    
    def test_add_metadata(self):
        """Test metadata addition to chunk"""
        chunk = TextChunk()
        chunk.add_metadata("token_count", 15)
        chunk.add_metadata("language", "en")
        
        assert chunk.metadata == {"token_count": 15, "language": "en"}
    
    def test_add_metadata_overwrite(self):
        """Test metadata overwrite in chunk"""
        chunk = TextChunk()
        chunk.add_metadata("token_count", 10)
        chunk.add_metadata("token_count", 15)
        
        assert chunk.metadata == {"token_count": 15}


class TestProcessingResult:
    """Test ProcessingResult entity"""
    
    def test_processing_result_creation(self):
        """Test processing result creation"""
        doc = Document(filename="test.pdf")
        chunks = [
            TextChunk(text="Chunk 1", chunk_index=0),
            TextChunk(text="Chunk 2", chunk_index=1)
        ]
        
        result = ProcessingResult(
            document=doc,
            chunks=chunks,
            processing_time_ms=1500,
            errors=[]
        )
        
        assert result.document == doc
        assert result.chunks == chunks
        assert result.processing_time_ms == 1500
        assert result.errors == []
        assert result.is_successful is True
    
    def test_processing_result_with_errors(self):
        """Test processing result with errors"""
        doc = Document(filename="test.pdf")
        doc.update_status(ProcessingStatus.FAILED)
        chunks = []
        
        result = ProcessingResult(
            document=doc,
            chunks=chunks,
            processing_time_ms=500,
            errors=["Processing failed", "Invalid format"]
        )
        
        assert result.document == doc
        assert result.chunks == chunks
        assert result.processing_time_ms == 500
        assert result.errors == ["Processing failed", "Invalid format"]
        assert result.is_successful is False
    
    def test_processing_result_successful_with_completed_status(self):
        """Test successful result with completed status"""
        doc = Document(filename="test.pdf")
        doc.update_status(ProcessingStatus.COMPLETED)
        chunks = [TextChunk(text="Test chunk")]
        
        result = ProcessingResult(
            document=doc,
            chunks=chunks,
            processing_time_ms=1000,
            errors=[]
        )
        
        assert result.is_successful is True
    
    def test_processing_result_unsuccessful_with_pending_status(self):
        """Test unsuccessful result with pending status"""
        doc = Document(filename="test.pdf")
        # Keep default PENDING status
        chunks = [TextChunk(text="Test chunk")]
        
        result = ProcessingResult(
            document=doc,
            chunks=chunks,
            processing_time_ms=1000,
            errors=[]
        )
        
        assert result.is_successful is False


class TestDocumentType:
    """Test DocumentType enum"""
    
    def test_document_type_values(self):
        """Test document type enum values"""
        assert DocumentType.PDF.value == "pdf"
        assert DocumentType.TXT.value == "txt"
        assert DocumentType.DOCX.value == "docx"
        assert DocumentType.HTML.value == "html"
        assert DocumentType.MD.value == "md"


class TestProcessingStatus:
    """Test ProcessingStatus enum"""
    
    def test_processing_status_values(self):
        """Test processing status enum values"""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.COMPLETED.value == "completed"
        assert ProcessingStatus.FAILED.value == "failed"
