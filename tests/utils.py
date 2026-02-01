"""Test utilities and helper functions"""

import json
import tempfile
import os
from uuid import uuid4
from typing import Dict, Any, List, Optional
from pathlib import Path


def create_temp_file(content: str, suffix: str = ".txt") -> str:
    """Create a temporary file with given content"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def create_temp_binary_file(content: bytes, suffix: str = ".bin") -> str:
    """Create a temporary binary file with given content"""
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def cleanup_temp_file(filepath: str) -> None:
    """Clean up temporary file"""
    try:
        os.unlink(filepath)
    except OSError:
        pass


def generate_sample_document_text(length: int = 1000) -> str:
    """Generate sample document text for testing"""
    sentences = [
        "This is a sample sentence for testing purposes.",
        "Machine learning is a subset of artificial intelligence.",
        "Natural language processing helps computers understand human language.",
        "Vector databases are essential for efficient similarity search.",
        "Embeddings represent text as numerical vectors in high-dimensional space.",
        "Retrieval-augmented generation combines search with language models.",
        "Document chunking improves retrieval accuracy.",
        "Semantic search finds documents based on meaning, not just keywords."
    ]
    
    text = ""
    while len(text) < length:
        text += " ".join(sentences) + " "
    
    return text[:length]


def create_sample_pdf_content() -> bytes:
    """Create minimal PDF content for testing"""
    # This is a minimal valid PDF header
    pdf_content = b"%PDF-1.4\n"
    pdf_content += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pdf_content += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    pdf_content += b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n"
    pdf_content += b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    pdf_content += b"5 0 obj\n<< /Length 44 >>\nstream\n"
    pdf_content += b"BT\n/F1 12 Tf\n72 720 Td\n(Hello World) Tj\nET\n"
    pdf_content += b"endstream\nendobj\n"
    pdf_content += b"xref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000264 00000 n\n0000000333 00000 n\n"
    pdf_content += b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
    pdf_content += b"startxref\n425\n"
    pdf_content += b"%%EOF"
    
    return pdf_content


def create_sample_json_data() -> Dict[str, Any]:
    """Create sample JSON data for testing"""
    return {
        "title": "Test Document",
        "content": "This is test content for the document.",
        "metadata": {
            "author": "Test Author",
            "created_date": "2024-01-01",
            "tags": ["test", "sample", "document"],
            "category": "testing"
        },
        "sections": [
            {
                "heading": "Introduction",
                "text": "This is the introduction section."
            },
            {
                "heading": "Main Content",
                "text": "This is the main content section."
            }
        ]
    }


def create_large_document_text(size_mb: int = 1) -> str:
    """Create large document text for testing size limits"""
    target_size = size_mb * 1024 * 1024  # Convert MB to bytes
    chunk = "This is a test sentence repeated to create a large document. " * 10
    chunk += "\n"
    
    text = ""
    while len(text.encode('utf-8')) < target_size:
        text += chunk
    
    return text


def create_special_characters_text() -> str:
    """Create text with special characters for testing encoding"""
    return (
        "English: Hello World!\n"
        "Russian: Привет мир!\n"
        "Chinese: 你好世界!\n"
        "Arabic: مرحبا بالعالم!\n"
        "Emoji: 🚀 📚 🧪\n"
        "Math: ∑∏∫∆∇∂\n"
        "Currency: $€£¥₹\n"
        "Symbols: ©®™§¶†‡•…‰‹›""''–—"
    )


def create_malformed_json() -> str:
    """Create malformed JSON for testing error handling"""
    return '{"key": "value", "incomplete": [1, 2, 3}'


def create_query_variations() -> List[str]:
    """Create various query types for testing"""
    return [
        "What is machine learning?",
        "How does neural network work?",
        "Explain artificial intelligence",
        "machine learning basics",
        "AI vs ML difference",
        "deep learning tutorial",
        "natural language processing",
        "computer vision applications",
        "reinforcement learning examples",
        "supervised learning algorithms"
    ]


def create_filter_combinations() -> List[Dict[str, Any]]:
    """Create various filter combinations for testing"""
    return [
        {},  # No filters
        {"category": "technology"},
        {"tags": ["important", "reviewed"]},
        {"date_range": {"start": "2024-01-01", "end": "2024-12-31"}},
        {"author": "John Doe", "category": "science"},
        {"min_score": 0.8, "max_results": 10},
        {"document_type": "pdf", "tags": ["research"]},
        {"complex": {"nested": {"filter": "value"}}}
    ]


def create_error_scenarios() -> Dict[str, Any]:
    """Create various error scenarios for testing"""
    return {
        "empty_query": "",
        "very_long_query": "query" * 1000,
        "special_chars_query": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
        "unicode_query": "🚀 What is AI? 机器学习",
        "null_values": {"query": None, "filters": None},
        "invalid_types": {"query": 123, "top_k": "five"},
        "negative_values": {"top_k": -1, "temperature": -0.5},
        "overflow_values": {"top_k": 999999999, "max_tokens": 999999999}
    }


def assert_valid_uuid(uuid_string: str) -> bool:
    """Check if string is a valid UUID"""
    try:
        uuid_obj = uuid4()
        uuid_obj.__class__(uuid_string)
        return True
    except ValueError:
        return False


def assert_valid_timestamp(timestamp: str) -> bool:
    """Check if string is a valid ISO timestamp"""
    try:
        from datetime import datetime
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


def calculate_test_coverage(test_functions: List[str], total_functions: List[str]) -> float:
    """Calculate test coverage percentage"""
    if not total_functions:
        return 0.0
    covered = len(set(test_functions) & set(total_functions))
    return (covered / len(total_functions)) * 100


def create_mock_embeddings(dimension: int = 384) -> List[float]:
    """Create mock embedding vector for testing"""
    import random
    return [random.uniform(-1, 1) for _ in range(dimension)]


def create_batch_test_data(batch_size: int = 10) -> List[Dict[str, Any]]:
    """Create batch of test data for performance testing"""
    batch_data = []
    for i in range(batch_size):
        batch_data.append({
            "id": str(uuid4()),
            "content": f"Test document content {i}",
            "metadata": {
                "batch_id": batch_size,
                "index": i,
                "timestamp": f"2024-01-{i+1:02d}T00:00:00"
            }
        })
    return batch_data


def measure_execution_time(func, *args, **kwargs) -> tuple:
    """Measure execution time of a function"""
    import time
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    execution_time = end_time - start_time
    return result, execution_time


def create_concurrent_test_data(num_concurrent: int = 5) -> List[Dict[str, Any]]:
    """Create data for concurrent testing"""
    return [
        {
            "query_id": str(uuid4()),
            "query": f"Concurrent test query {i}",
            "expected_delay": i * 0.1  # Stagger the requests
        }
        for i in range(num_concurrent)
    ]


def validate_response_structure(response_data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validate that response contains all required fields"""
    for field in required_fields:
        if field not in response_data:
            return False
    return True


def create_test_scenarios() -> Dict[str, Dict[str, Any]]:
    """Create comprehensive test scenarios"""
    return {
        "happy_path": {
            "description": "Normal successful operation",
            "expected_status": 200,
            "should_succeed": True
        },
        "invalid_input": {
            "description": "Invalid input parameters",
            "expected_status": 400,
            "should_succeed": False
        },
        "not_found": {
            "description": "Resource not found",
            "expected_status": 404,
            "should_succeed": False
        },
        "server_error": {
            "description": "Internal server error",
            "expected_status": 500,
            "should_succeed": False
        },
        "unauthorized": {
            "description": "Unauthorized access",
            "expected_status": 401,
            "should_succeed": False
        }
    }


class TestDataGenerator:
    """Class for generating various test data"""
    
    def __init__(self):
        self.document_counter = 0
        self.query_counter = 0
    
    def next_document_id(self) -> str:
        """Generate next document ID"""
        self.document_counter += 1
        return f"doc_{self.document_counter:04d}"
    
    def next_query_id(self) -> str:
        """Generate next query ID"""
        self.query_counter += 1
        return f"query_{self.query_counter:04d}"
    
    def generate_document(self, length: int = 500) -> Dict[str, Any]:
        """Generate a complete document"""
        return {
            "id": str(uuid4()),
            "doc_id": self.next_document_id(),
            "content": generate_sample_document_text(length),
            "metadata": create_sample_json_data()["metadata"],
            "created_at": "2024-01-01T00:00:00"
        }
    
    def generate_query(self, query_type: str = "semantic") -> Dict[str, Any]:
        """Generate a complete query"""
        queries = create_query_variations()
        return {
            "id": str(uuid4()),
            "query_id": self.next_query_id(),
            "query": queries[self.query_counter % len(queries)],
            "query_type": query_type,
            "top_k": 5,
            "filters": {},
            "metadata": {"test": True}
        }


# Performance testing utilities
class PerformanceProfiler:
    """Simple performance profiler for tests"""
    
    def __init__(self):
        self.timings = {}
    
    def time_function(self, name: str):
        """Decorator to time function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                
                if name not in self.timings:
                    self.timings[name] = []
                self.timings[name].append(end_time - start_time)
                
                return result
            return wrapper
        return decorator
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """Get performance statistics for a function"""
        if name not in self.timings:
            return {}
        
        times = self.timings[name]
        return {
            "count": len(times),
            "total": sum(times),
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times)
        }
    
    def reset(self):
        """Reset all timings"""
        self.timings = {}


# Mock response builders
class MockResponseBuilder:
    """Builder for creating mock API responses"""
    
    @staticmethod
    def success_response(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a success response"""
        return {
            "success": True,
            "data": data,
            "error": None
        }
    
    @staticmethod
    def error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "success": False,
            "data": None,
            "error": {
                "message": message,
                "status_code": status_code
            }
        }
    
    @staticmethod
    def paginated_response(items: List[Any], page: int = 1, per_page: int = 10, total: Optional[int] = None) -> Dict[str, Any]:
        """Create a paginated response"""
        if total is None:
            total = len(items)
        
        return {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
