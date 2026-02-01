"""Unit tests for query domain entities"""

import pytest
from datetime import datetime
from uuid import uuid4

from shared.models.base import (
    QueryRequest, RetrievalResult, GenerationRequest, 
    QueryType, ModelType
)


class TestQueryRequest:
    """Test QueryRequest entity"""
    
    def test_query_request_creation_with_defaults(self):
        """Test query request creation with default values"""
        request = QueryRequest(query="What is AI?")
        
        assert request.query_id is not None
        assert request.query == "What is AI?"
        assert request.query_type == QueryType.SEMANTIC
        assert request.top_k == 5
        assert request.filters == {}
        assert request.metadata == {}
    
    def test_query_request_creation_with_values(self):
        """Test query request creation with specific values"""
        query_id = str(uuid4())
        filters = {"document_type": "pdf", "date_range": {"start": "2024-01-01"}}
        metadata = {"user_id": "test_user", "session_id": "abc123"}
        
        request = QueryRequest(
            query_id=query_id,
            query="Machine learning basics",
            query_type=QueryType.HYBRID,
            top_k=10,
            filters=filters,
            metadata=metadata
        )
        
        assert request.query_id == query_id
        assert request.query == "Machine learning basics"
        assert request.query_type == QueryType.HYBRID
        assert request.top_k == 10
        assert request.filters == filters
        assert request.metadata == metadata
    
    def test_query_request_validation_top_k_bounds(self):
        """Test query request validation for top_k bounds"""
        # Test minimum boundary
        request_min = QueryRequest(query="test", top_k=1)
        assert request_min.top_k == 1
        
        # Test maximum boundary
        request_max = QueryRequest(query="test", top_k=100)
        assert request_max.top_k == 100
        
        # Test invalid values (should raise validation error)
        with pytest.raises(ValueError):
            QueryRequest(query="test", top_k=0)
        
        with pytest.raises(ValueError):
            QueryRequest(query="test", top_k=101)
    
    def test_query_request_empty_query(self):
        """Test query request with empty query"""
        request = QueryRequest(query="")
        assert request.query == ""
        assert request.query_id is not None
    
    def test_query_request_long_query(self):
        """Test query request with long query"""
        long_query = "What is " + "very " * 100 + "long?"
        request = QueryRequest(query=long_query)
        assert request.query == long_query


class TestRetrievalResult:
    """Test RetrievalResult entity"""
    
    def test_retrieval_result_creation_with_defaults(self):
        """Test retrieval result creation with default values"""
        result = RetrievalResult(
            chunk_id=str(uuid4()),
            document_id=str(uuid4()),
            text="Relevant text",
            score=0.85
        )
        
        assert result.chunk_id is not None
        assert result.document_id is not None
        assert result.text == "Relevant text"
        assert result.score == 0.85
        assert result.metadata == {}
    
    def test_retrieval_result_creation_with_values(self):
        """Test retrieval result creation with specific values"""
        chunk_id = str(uuid4())
        document_id = str(uuid4())
        metadata = {"page": 1, "section": "introduction", "confidence": 0.9}
        
        result = RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            text="Machine learning is a subset of AI",
            score=0.95,
            metadata=metadata
        )
        
        assert result.chunk_id == chunk_id
        assert result.document_id == document_id
        assert result.text == "Machine learning is a subset of AI"
        assert result.score == 0.95
        assert result.metadata == metadata
    
    def test_retrieval_result_score_bounds(self):
        """Test retrieval result score boundaries"""
        chunk_id = str(uuid4())
        document_id = str(uuid4())
        
        # Test minimum score
        result_min = RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            text="test",
            score=0.0
        )
        assert result_min.score == 0.0
        
        # Test maximum score
        result_max = RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            text="test",
            score=1.0
        )
        assert result_max.score == 1.0
    
    def test_retrieval_result_empty_text(self):
        """Test retrieval result with empty text"""
        result = RetrievalResult(
            chunk_id=str(uuid4()),
            document_id=str(uuid4()),
            text="",
            score=0.5
        )
        assert result.text == ""


class TestGenerationRequest:
    """Test GenerationRequest entity"""
    
    def test_generation_request_creation_with_defaults(self):
        """Test generation request creation with default values"""
        context = [
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="Context text",
                score=0.9
            )
        ]
        
        request = GenerationRequest(
            query="Summarize this",
            context=context,
            model_name="gpt-3.5-turbo"
        )
        
        assert request.request_id is not None
        assert request.query == "Summarize this"
        assert request.context == context
        assert request.model_name == "gpt-3.5-turbo"
        assert request.max_tokens == 512
        assert request.temperature == 0.7
        assert request.metadata == {}
    
    def test_generation_request_creation_with_values(self):
        """Test generation request creation with specific values"""
        request_id = str(uuid4())
        context = [
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="First context",
                score=0.9
            ),
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="Second context",
                score=0.8
            )
        ]
        metadata = {"user_id": "test_user", "conversation_id": "conv123"}
        
        request = GenerationRequest(
            request_id=request_id,
            query="Explain in detail",
            context=context,
            model_name="gpt-4",
            max_tokens=1024,
            temperature=0.5,
            metadata=metadata
        )
        
        assert request.request_id == request_id
        assert request.query == "Explain in detail"
        assert request.context == context
        assert request.model_name == "gpt-4"
        assert request.max_tokens == 1024
        assert request.temperature == 0.5
        assert request.metadata == metadata
    
    def test_generation_request_validation_max_tokens_bounds(self):
        """Test generation request validation for max_tokens bounds"""
        context = []
        
        # Test minimum boundary
        request_min = GenerationRequest(
            query="test",
            context=context,
            model_name="test-model",
            max_tokens=1
        )
        assert request_min.max_tokens == 1
        
        # Test maximum boundary
        request_max = GenerationRequest(
            query="test",
            context=context,
            model_name="test-model",
            max_tokens=4096
        )
        assert request_max.max_tokens == 4096
        
        # Test invalid values
        with pytest.raises(ValueError):
            GenerationRequest(
                query="test",
                context=context,
                model_name="test-model",
                max_tokens=0
            )
        
        with pytest.raises(ValueError):
            GenerationRequest(
                query="test",
                context=context,
                model_name="test-model",
                max_tokens=4097
            )
    
    def test_generation_request_validation_temperature_bounds(self):
        """Test generation request validation for temperature bounds"""
        context = []
        
        # Test minimum boundary
        request_min = GenerationRequest(
            query="test",
            context=context,
            model_name="test-model",
            temperature=0.0
        )
        assert request_min.temperature == 0.0
        
        # Test maximum boundary
        request_max = GenerationRequest(
            query="test",
            context=context,
            model_name="test-model",
            temperature=2.0
        )
        assert request_max.temperature == 2.0
        
        # Test invalid values
        with pytest.raises(ValueError):
            GenerationRequest(
                query="test",
                context=context,
                model_name="test-model",
                temperature=-0.1
            )
        
        with pytest.raises(ValueError):
            GenerationRequest(
                query="test",
                context=context,
                model_name="test-model",
                temperature=2.1
            )
    
    def test_generation_request_empty_context(self):
        """Test generation request with empty context"""
        request = GenerationRequest(
            query="Generate without context",
            context=[],
            model_name="test-model"
        )
        assert request.context == []
    
    def test_generation_request_large_context(self):
        """Test generation request with large context"""
        context = []
        for i in range(50):
            context.append(
                RetrievalResult(
                    chunk_id=str(uuid4()),
                    document_id=str(uuid4()),
                    text=f"Context chunk {i}",
                    score=0.9 - (i * 0.01)
                )
            )
        
        request = GenerationRequest(
            query="Process large context",
            context=context,
            model_name="test-model"
        )
        assert len(request.context) == 50


class TestQueryType:
    """Test QueryType enum"""
    
    def test_query_type_values(self):
        """Test query type enum values"""
        assert QueryType.SEMANTIC.value == "semantic"
        assert QueryType.HYBRID.value == "hybrid"
        assert QueryType.KEYWORD.value == "keyword"


class TestModelType:
    """Test ModelType enum"""
    
    def test_model_type_values(self):
        """Test model type enum values"""
        assert ModelType.EMBEDDING.value == "embedding"
        assert ModelType.GENERATION.value == "generation"
        assert ModelType.RERANKING.value == "reranking"
