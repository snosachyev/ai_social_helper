#!/usr/bin/env python3
"""Simple test runner for document entities"""

import sys
import os
from datetime import datetime
from uuid import uuid4

# Add the service path to Python path
service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../services/document-service/src'))
sys.path.insert(0, service_path)

from domain.entities.document import Document, TextChunk, ProcessingResult, DocumentType, ProcessingStatus

def test_document_creation():
    """Test document creation with default values"""
    print("🧪 Testing document creation...")
    
    doc = Document()
    
    assert doc.document_id is not None
    assert doc.filename == ""
    assert doc.file_type == DocumentType.TXT
    assert doc.size_bytes == 0
    assert doc.status == ProcessingStatus.PENDING
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)
    assert doc.metadata == {}
    
    print("✅ Document creation with defaults works")

def test_document_creation_with_values():
    """Test document creation with specific values"""
    print("🧪 Testing document creation with values...")
    
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
    
    print("✅ Document creation with values works")

def test_document_update_status():
    """Test status update functionality"""
    print("🧪 Testing document status update...")
    
    doc = Document()
    original_updated_at = doc.updated_at
    
    import time
    time.sleep(0.01)
    
    doc.update_status(ProcessingStatus.PROCESSING)
    
    assert doc.status == ProcessingStatus.PROCESSING
    assert doc.updated_at > original_updated_at
    
    print("✅ Document status update works")

def test_document_add_metadata():
    """Test metadata addition"""
    print("🧪 Testing document metadata addition...")
    
    doc = Document()
    original_updated_at = doc.updated_at
    
    import time
    time.sleep(0.01)
    
    doc.add_metadata("author", "Test Author")
    doc.add_metadata("category", "Testing")
    
    assert doc.metadata == {"author": "Test Author", "category": "Testing"}
    assert doc.updated_at > original_updated_at
    
    print("✅ Document metadata addition works")

def test_text_chunk_creation():
    """Test text chunk creation"""
    print("🧪 Testing text chunk creation...")
    
    chunk = TextChunk()
    
    assert chunk.chunk_id is not None
    assert chunk.document_id == ""
    assert chunk.text == ""
    assert chunk.chunk_index == 0
    assert chunk.start_char == 0
    assert chunk.end_char == 0
    assert chunk.metadata == {}
    
    print("✅ Text chunk creation works")

def test_processing_result():
    """Test processing result"""
    print("🧪 Testing processing result...")
    
    doc = Document(filename="test.pdf")
    doc.update_status(ProcessingStatus.COMPLETED)  # Set status to COMPLETED
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
    
    print("✅ Processing result works")

def run_all_tests():
    """Run all tests"""
    print("🚀 Starting document entity tests...\n")
    
    try:
        test_document_creation()
        test_document_creation_with_values()
        test_document_update_status()
        test_document_add_metadata()
        test_text_chunk_creation()
        test_processing_result()
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
