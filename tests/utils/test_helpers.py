"""Test helper utilities"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional
import httpx


def create_test_file(content: str, suffix: str = ".txt") -> str:
    """Create a temporary test file with given content
    
    Args:
        content: File content
        suffix: File suffix/extension
        
    Returns:
        Path to created temporary file
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    
    temp_file = tempfile.NamedTemporaryFile(
        mode='wb',
        suffix=suffix,
        delete=False
    )
    
    try:
        temp_file.write(content)
        temp_file.flush()
        return temp_file.name
    finally:
        temp_file.close()


def cleanup_test_files(file_paths: List[str]) -> None:
    """Clean up test files
    
    Args:
        file_paths: List of file paths to delete
    """
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            # Ignore cleanup errors
            pass


async def get_auth_token(client: httpx.AsyncClient, 
                        email: str = "test@example.com", 
                        password: str = "test") -> str:
    """Get authentication token
    
    Args:
        client: HTTP client
        email: User email
        password: User password
        
    Returns:
        JWT token string
    """
    response = await client.post(
        "http://localhost:8007/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to get auth token: {response.status_code}")
    
    data = response.json()
    return data["access_token"]


def generate_sample_document_text(length: int = 1000) -> str:
    """Generate sample document text
    
    Args:
        length: Desired text length
        
    Returns:
        Generated text
    """
    base_text = (
        "Machine learning is a method of data analysis that automates analytical model building. "
        "It is a branch of artificial intelligence based on the idea that systems can learn from data, "
        "identify patterns and make decisions with minimal human intervention. "
        "Deep learning is a type of machine learning that trains a computer to perform human-like tasks. "
        "Natural language processing enables computers to understand and interpret human language. "
        "Computer vision allows machines to interpret and make decisions based on visual data. "
    )
    
    # Repeat text to reach desired length
    result = ""
    while len(result) < length:
        result += base_text
    
    return result[:length]


def create_sample_pdf_content() -> bytes:
    """Create sample PDF content (minimal valid PDF)
    
    Returns:
        PDF file content as bytes
    """
    # Minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Sample PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000054 00000 n 
0000000123 00000 n 
0000000201 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
321
%%EOF"""
    
    return pdf_content


def create_sample_docx_content() -> bytes:
    """Create sample DOCX content (minimal)
    
    Returns:
        DOCX file content as bytes
    """
    # This is a very minimal DOCX structure
    # In real tests, you might want to use python-docx to create proper DOCX files
    docx_content = (
        b'PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb9\x1e\x9f'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'[Content_Types].xmlPK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00'
    )
    
    return docx_content


def assert_valid_document_metadata(metadata: dict) -> None:
    """Assert that document metadata is valid
    
    Args:
        metadata: Document metadata dictionary
    """
    required_fields = ["document_id", "filename", "file_type", "size_bytes", "status"]
    
    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"
    
    assert isinstance(metadata["document_id"], str)
    assert isinstance(metadata["filename"], str)
    assert isinstance(metadata["file_type"], str)
    assert isinstance(metadata["size_bytes"], int)
    assert isinstance(metadata["status"], str)
    
    assert len(metadata["document_id"]) > 0
    assert len(metadata["filename"]) > 0
    assert metadata["size_bytes"] >= 0
    assert metadata["status"] in ["pending", "processing", "completed", "failed"]


def assert_valid_chunk(chunk: dict) -> None:
    """Assert that text chunk is valid
    
    Args:
        chunk: Chunk dictionary
    """
    required_fields = ["chunk_id", "document_id", "text", "chunk_index", "start_char", "end_char"]
    
    for field in required_fields:
        assert field in chunk, f"Missing required field: {field}"
    
    assert isinstance(chunk["chunk_id"], str)
    assert isinstance(chunk["document_id"], str)
    assert isinstance(chunk["text"], str)
    assert isinstance(chunk["chunk_index"], int)
    assert isinstance(chunk["start_char"], int)
    assert isinstance(chunk["end_char"], int)
    
    assert len(chunk["chunk_id"]) > 0
    assert len(chunk["document_id"]) > 0
    assert chunk["chunk_index"] >= 0
    assert chunk["start_char"] >= 0
    assert chunk["end_char"] >= chunk["start_char"]


def assert_valid_query_response(response: dict) -> None:
    """Assert that query response is valid
    
    Args:
        response: Query response dictionary
    """
    required_fields = ["query_id", "results", "processing_time_ms"]
    
    for field in required_fields:
        assert field in response, f"Missing required field: {field}"
    
    assert isinstance(response["query_id"], str)
    assert isinstance(response["results"], list)
    assert isinstance(response["processing_time_ms"], int)
    
    assert len(response["query_id"]) > 0
    assert response["processing_time_ms"] >= 0
    
    # Validate results
    for result in response["results"]:
        assert_valid_retrieval_result(result)


def assert_valid_retrieval_result(result: dict) -> None:
    """Assert that retrieval result is valid
    
    Args:
        result: Retrieval result dictionary
    """
    required_fields = ["chunk_id", "document_id", "text", "score"]
    
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"
    
    assert isinstance(result["chunk_id"], str)
    assert isinstance(result["document_id"], str)
    assert isinstance(result["text"], str)
    assert isinstance(result["score"], (int, float))
    
    assert len(result["chunk_id"]) > 0
    assert len(result["document_id"]) > 0
    assert 0 <= result["score"] <= 1


class PerformanceProfiler:
    """Simple performance profiler for tests"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start profiling"""
        import time
        self.start_time = time.time()
    
    def stop(self):
        """Stop profiling"""
        import time
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0
    
    def assert_max_duration(self, max_ms: float):
        """Assert that duration is within maximum allowed time"""
        assert self.duration_ms <= max_ms, f"Duration {self.duration_ms}ms exceeds maximum {max_ms}ms"
