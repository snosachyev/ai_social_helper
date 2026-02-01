#!/usr/bin/env python3
"""Simple pytest test for document entities"""

import pytest
import sys
import os
from datetime import datetime
from uuid import uuid4

# Add service path
service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../services/document-service/src'))
sys.path.insert(0, service_path)

from domain.entities.document import Document, TextChunk, ProcessingResult, DocumentType, ProcessingStatus

class TestDocumentEntities:
    """Test document entities with pytest"""
    
    def test_document_creation_defaults(self):
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
        created_at = datetime.now()
        
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
    
    def test_document_update_status(self):
        """Test status update functionality"""
        doc = Document()
        original_updated_at = doc.updated_at
        
        import time
        time.sleep(0.01)
        
        doc.update_status(ProcessingStatus.PROCESSING)
        
        assert doc.status == ProcessingStatus.PROCESSING
        assert doc.updated_at > original_updated_at
    
    def test_document_add_metadata(self):
        """Test metadata addition"""
        doc = Document()
        original_updated_at = doc.updated_at
        
        import time
        time.sleep(0.01)
        
        doc.add_metadata("author", "Test Author")
        doc.add_metadata("category", "Testing")
        
        assert doc.metadata == {"author": "Test Author", "category": "Testing"}
        assert doc.updated_at > original_updated_at
    
    def test_text_chunk_creation(self):
        """Test text chunk creation"""
        chunk = TextChunk()
        
        assert chunk.chunk_id is not None
        assert chunk.document_id == ""
        assert chunk.text == ""
        assert chunk.chunk_index == 0
        assert chunk.start_char == 0
        assert chunk.end_char == 0
        assert chunk.metadata == {}
    
    def test_processing_result_successful(self):
        """Test successful processing result"""
        doc = Document(filename="test.pdf")
        doc.update_status(ProcessingStatus.COMPLETED)
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
    
    def test_processing_result_failed(self):
        """Test failed processing result"""
        doc = Document(filename="test.pdf")
        doc.update_status(ProcessingStatus.FAILED)
        chunks = []
        
        result = ProcessingResult(
            document=doc,
            chunks=chunks,
            processing_time_ms=500,
            errors=["Processing failed", "Invalid format"]
        )
        
        assert result.is_successful is False
        assert len(result.errors) == 2
        assert "Processing failed" in result.errors
