"""Tests for query controller endpoints"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json

from src.domain.entities.query import QueryType
from src.domain.entities.embedding import RetrievalResult
from src.application.services.dependency_injection import get_container


class TestProcessQuery:
    """Test query processing endpoint"""
    
    def test_process_query_success(self, client, mock_query_use_case, mock_tracing_service, sample_query_response):
        """Test successful query processing"""
        mock_query_use_case.execute_query.return_value = sample_query_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {
                    "query": "What is machine learning?",
                    "query_type": "semantic",
                    "top_k": 5,
                    "filters": {"category": "technology"},
                    "metadata": {"user_id": "test_user"}
                }
                response = client.post("/query/", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["query_id"] == str(sample_query_response.query_id)
        assert "results" in data
        assert "processing_time_ms" in data
        assert "guard_result" in data
        assert "metadata" in data
        
        # Verify results structure
        results = data["results"]
        assert len(results) == len(sample_query_response.results)
        for i, result in enumerate(results):
            assert "chunk_id" in result
            assert "document_id" in result
            assert "text" in result
            assert "score" in result
            assert "metadata" in result
        
        # Verify guard result
        guard_result = data["guard_result"]
        assert guard_result["is_allowed"] == sample_query_response.guard_result.is_allowed
        assert guard_result["reason"] == sample_query_response.guard_result.reason
        assert guard_result["risk_score"] == sample_query_response.guard_result.risk_score
        
        # Verify tracing was called
        mock_tracing_service.trace_query.assert_called_once()
    
    def test_process_query_with_defaults(self, client, mock_query_use_case, mock_tracing_service, sample_query_response):
        """Test query processing with default values"""
        mock_query_use_case.execute_query.return_value = sample_query_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                # Minimal query data
                query_data = {"query": "test query"}
                response = client.post("/query/", json=query_data)
        
        assert response.status_code == 200
        
        # Verify default values were used
        call_args = mock_query_use_case.execute_query.call_args[0][0]
        assert call_args.query == "test query"
        assert call_args.query_type == QueryType.SEMANTIC
        assert call_args.top_k == 5
        assert call_args.filters == {}
        assert call_args.metadata == {}
    
    def test_process_query_invalid_query_type(self, client, mock_query_use_case, mock_tracing_service):
        """Test query processing with invalid query type"""
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {
                    "query": "test query",
                    "query_type": "invalid_type"
                }
                response = client.post("/query/", json=query_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid request" in data["detail"]
    
    def test_process_query_use_case_exception(self, client, mock_query_use_case, mock_tracing_service):
        """Test query processing when use case raises exception"""
        mock_query_use_case.execute_query.side_effect = Exception("Search service error")
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {"query": "test query"}
                response = client.post("/query/", json=query_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "Query processing failed" in data["detail"]
    
    def test_process_query_empty_query(self, client, mock_query_use_case, mock_tracing_service):
        """Test query processing with empty query"""
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {"query": ""}
                response = client.post("/query/", json=query_data)
        
        # Should still work (empty query might be valid in some contexts)
        assert response.status_code == 200


class TestGenerateResponse:
    """Test text generation endpoint"""
    
    def test_generate_response_success(self, client, mock_query_use_case, mock_tracing_service, sample_generation_response):
        """Test successful text generation"""
        mock_query_use_case.execute_generation.return_value = sample_generation_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "Summarize the following text:",
                    "context": [
                        {
                            "chunk_id": str(uuid4()),
                            "document_id": str(uuid4()),
                            "text": "This is context text.",
                            "score": 0.9,
                            "metadata": {"source": "test"}
                        }
                    ],
                    "model_name": "gpt-3.5-turbo",
                    "max_tokens": 512,
                    "temperature": 0.7,
                    "metadata": {"user_id": "test_user"}
                }
                response = client.post("/query/generate", json=generation_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == str(sample_generation_response.request_id)
        assert data["response"] == sample_generation_response.response
        assert data["model_name"] == sample_generation_response.model_name
        assert data["tokens_used"] == sample_generation_response.tokens_used
        assert data["processing_time_ms"] == sample_generation_response.processing_time_ms
        assert "guard_result" in data
        assert "metadata" in data
        
        # Verify guard result
        guard_result = data["guard_result"]
        assert guard_result["is_allowed"] == sample_generation_response.guard_result.is_allowed
        assert guard_result["reason"] == sample_generation_response.guard_result.reason
        assert guard_result["risk_score"] == sample_generation_response.guard_result.risk_score
    
    def test_generate_response_with_defaults(self, client, mock_query_use_case, mock_tracing_service, sample_generation_response):
        """Test text generation with default values"""
        mock_query_use_case.execute_generation.return_value = sample_generation_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                # Minimal generation data
                generation_data = {
                    "query": "test query",
                    "context": []
                }
                response = client.post("/query/generate", json=generation_data)
        
        assert response.status_code == 200
        
        # Verify default values were used
        call_args = mock_query_use_case.execute_generation.call_args[0][0]
        assert call_args.query == "test query"
        assert call_args.context == []
        assert call_args.model_name == "default"
        assert call_args.max_tokens == 512
        assert call_args.temperature == 0.7
        assert call_args.metadata == {}
    
    def test_generate_response_invalid_context_format(self, client, mock_query_use_case, mock_tracing_service):
        """Test text generation with invalid context format"""
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "test query",
                    "context": [
                        {
                            "chunk_id": "invalid-uuid",  # Invalid UUID format
                            "document_id": str(uuid4()),
                            "text": "context text"
                        }
                    ]
                }
                response = client.post("/query/generate", json=generation_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid request" in data["detail"]
    
    def test_generate_response_use_case_exception(self, client, mock_query_use_case, mock_tracing_service):
        """Test text generation when use case raises exception"""
        mock_query_use_case.execute_generation.side_effect = Exception("Generation service error")
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "test query",
                    "context": []
                }
                response = client.post("/query/generate", json=generation_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "Generation failed" in data["detail"]
    
    def test_generate_response_empty_query(self, client, mock_query_use_case, mock_tracing_service, sample_generation_response):
        """Test text generation with empty query"""
        mock_query_use_case.execute_generation.return_value = sample_generation_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "",
                    "context": []
                }
                response = client.post("/query/generate", json=generation_data)
        
        # Should still work (empty query might be valid)
        assert response.status_code == 200


class TestGetQuerySuggestions:
    """Test query suggestions endpoint"""
    
    def test_get_query_suggestions_success(self, client, mock_query_use_case):
        """Test successful query suggestions retrieval"""
        suggestions = ["machine learning basics", "deep learning tutorial", "AI fundamentals"]
        mock_query_use_case.get_query_suggestions.return_value = suggestions
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/suggestions?partial_query=machine&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["partial_query"] == "machine"
        assert data["suggestions"] == suggestions
        assert data["count"] == len(suggestions)
        
        # Verify use case was called with correct parameters
        mock_query_use_case.get_query_suggestions.assert_called_once_with("machine", 5)
    
    def test_get_query_suggestions_defaults(self, client, mock_query_use_case):
        """Test query suggestions with default limit"""
        mock_query_use_case.get_query_suggestions.return_value = []
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/suggestions?partial_query=test")
        
        assert response.status_code == 200
        
        # Verify default limit was used
        mock_query_use_case.get_query_suggestions.assert_called_once_with("test", 5)
    
    def test_get_query_suggestions_use_case_exception(self, client, mock_query_use_case):
        """Test query suggestions when use case raises exception"""
        mock_query_use_case.get_query_suggestions.side_effect = Exception("Suggestion service error")
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/suggestions?partial_query=test")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get suggestions" in data["detail"]


class TestGetQueryHistory:
    """Test query history endpoint"""
    
    def test_get_query_history_success(self, client, mock_query_use_case):
        """Test successful query history retrieval"""
        history = [
            {"query": "machine learning", "timestamp": "2024-01-01T10:00:00"},
            {"query": "deep learning", "timestamp": "2024-01-01T09:30:00"}
        ]
        mock_query_use_case.get_query_history.return_value = history
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/history?user_id=test_user&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"
        assert data["history"] == history
        assert data["count"] == len(history)
        
        # Verify use case was called with correct parameters
        mock_query_use_case.get_query_history.assert_called_once_with("test_user", 10)
    
    def test_get_query_history_defaults(self, client, mock_query_use_case):
        """Test query history with default limit"""
        mock_query_use_case.get_query_history.return_value = []
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/history?user_id=test_user")
        
        assert response.status_code == 200
        
        # Verify default limit was used
        mock_query_use_case.get_query_history.assert_called_once_with("test_user", 10)
    
    def test_get_query_history_use_case_exception(self, client, mock_query_use_case):
        """Test query history when use case raises exception"""
        mock_query_use_case.get_query_history.side_effect = Exception("History service error")
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            mock_get_query.return_value = mock_query_use_case
            
            response = client.get("/query/history?user_id=test_user")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get history" in data["detail"]


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/query/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "query-service"
        assert data["version"] == "1.0.0"


class TestAsyncQueryProcessing:
    """Test async query processing with httpx client"""
    
    @pytest.mark.asyncio
    async def test_async_process_query_success(self, async_client, mock_query_use_case, mock_tracing_service, sample_query_response):
        """Test successful async query processing"""
        mock_query_use_case.execute_query.return_value = sample_query_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {
                    "query": "What is AI?",
                    "query_type": "semantic",
                    "top_k": 3
                }
                response = await async_client.post("/query/", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["query_id"] == str(sample_query_response.query_id)
        assert len(data["results"]) == len(sample_query_response.results)
    
    @pytest.mark.asyncio
    async def test_async_generate_response_success(self, async_client, mock_query_use_case, mock_tracing_service, sample_generation_response):
        """Test successful async text generation"""
        mock_query_use_case.execute_generation.return_value = sample_generation_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "Summarize this:",
                    "context": [
                        {
                            "chunk_id": str(uuid4()),
                            "document_id": str(uuid4()),
                            "text": "Context text",
                            "score": 0.9
                        }
                    ]
                }
                response = await async_client.post("/query/generate", json=generation_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == str(sample_generation_response.request_id)
        assert data["response"] == sample_generation_response.response


class TestQueryValidation:
    """Test query input validation"""
    
    def test_query_with_large_top_k(self, client, mock_query_use_case, mock_tracing_service, sample_query_response):
        """Test query with large top_k value"""
        mock_query_use_case.execute_query.return_value = sample_query_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {
                    "query": "test query",
                    "top_k": 1000  # Very large value
                }
                response = client.post("/query/", json=query_data)
        
        # Should still work (validation might be at use case level)
        assert response.status_code == 200
        
        # Verify the large value was passed through
        call_args = mock_query_use_case.execute_query.call_args[0][0]
        assert call_args.top_k == 1000
    
    def test_generation_with_invalid_temperature(self, client, mock_query_use_case, mock_tracing_service):
        """Test generation with invalid temperature value"""
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                generation_data = {
                    "query": "test query",
                    "context": [],
                    "temperature": 2.5  # Invalid temperature (should be 0-1)
                }
                response = client.post("/query/generate", json=generation_data)
        
        # Should still work (validation might be at use case level)
        assert response.status_code == 200
        
        # Verify the invalid value was passed through
        call_args = mock_query_use_case.execute_generation.call_args[0][0]
        assert call_args.temperature == 2.5
    
    def test_query_with_complex_filters(self, client, mock_query_use_case, mock_tracing_service, sample_query_response):
        """Test query with complex filter structure"""
        mock_query_use_case.execute_query.return_value = sample_query_response
        
        with patch('src.presentation.api.query_controller.get_query_use_case') as mock_get_query:
            with patch('src.presentation.api.query_controller.get_tracing_service') as mock_get_trace:
                mock_get_query.return_value = mock_query_use_case
                mock_get_trace.return_value = mock_tracing_service
                
                query_data = {
                    "query": "test query",
                    "filters": {
                        "date_range": {
                            "start": "2024-01-01",
                            "end": "2024-12-31"
                        },
                        "tags": ["important", "reviewed"],
                        "author": "John Doe",
                        "min_score": 0.8
                    }
                }
                response = client.post("/query/", json=query_data)
        
        assert response.status_code == 200
        
        # Verify complex filters were passed through
        call_args = mock_query_use_case.execute_query.call_args[0][0]
        assert call_args.filters["date_range"]["start"] == "2024-01-01"
        assert call_args.filters["tags"] == ["important", "reviewed"]
        assert call_args.filters["author"] == "John Doe"
        assert call_args.filters["min_score"] == 0.8
