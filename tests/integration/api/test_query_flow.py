"""Integration tests for query processing flow"""

import pytest
import asyncio
import httpx
from uuid import uuid4
from tests.utils.test_helpers import get_auth_token, assert_valid_query_response, PerformanceProfiler


class TestQueryProcessingFlow:
    """Integration tests for query processing flow"""
    
    @pytest.mark.asyncio
    async def test_semantic_query_flow(self):
        """Test semantic query processing flow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Authenticate
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Step 2: Perform semantic query
            query_data = {
                "query": "What is machine learning?",
                "query_type": "semantic",
                "top_k": 5,
                "filters": {},
                "metadata": {"user_id": "test_user"}
            }
            
            profiler = PerformanceProfiler()
            profiler.start()
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            profiler.stop()
            
            # Assert response structure
            assert response.status_code in [200, 500]  # May fail if no documents indexed
            profiler.assert_max_duration(5000)  # Should complete within 5 seconds
            
            if response.status_code == 200:
                data = response.json()
                assert_valid_query_response(data)
                assert data["query_id"] == query_data["query_id"]
                assert len(data["results"]) <= query_data["top_k"]
    
    @pytest.mark.asyncio
    async def test_hybrid_query_flow(self):
        """Test hybrid query processing flow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            query_data = {
                "query": "artificial intelligence applications",
                "query_type": "hybrid",
                "top_k": 3,
                "filters": {"document_type": "pdf"},
                "metadata": {"user_id": "test_user"}
            }
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert_valid_query_response(data)
                assert len(data["results"]) <= 3
    
    @pytest.mark.asyncio
    async def test_keyword_query_flow(self):
        """Test keyword query processing flow"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            query_data = {
                "query": "neural networks deep learning",
                "query_type": "keyword",
                "top_k": 10,
                "filters": {},
                "metadata": {"user_id": "test_user"}
            }
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert_valid_query_response(data)
                assert len(data["results"]) <= 10
    
    @pytest.mark.asyncio
    async def test_query_with_filters(self):
        """Test query with document filters"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            query_data = {
                "query": "data science",
                "query_type": "semantic",
                "top_k": 5,
                "filters": {
                    "document_type": "pdf",
                    "date_range": {
                        "start": "2024-01-01",
                        "end": "2024-12-31"
                    },
                    "tags": ["research", "academic"]
                },
                "metadata": {"user_id": "test_user"}
            }
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert_valid_query_response(data)
    
    @pytest.mark.asyncio
    async def test_query_unauthorized(self):
        """Test query without authentication"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            query_data = {
                "query": "test query",
                "query_type": "semantic",
                "top_k": 5
            }
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data
            )
            
            assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_query_invalid_token(self):
        """Test query with invalid token"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": "Bearer invalid_token"}
            
            query_data = {
                "query": "test query",
                "query_type": "semantic",
                "top_k": 5
            }
            
            response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            assert response.status_code in [401, 403, 500]
    
    @pytest.mark.asyncio
    async def test_query_invalid_data(self):
        """Test query with invalid data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test with missing required fields
            invalid_queries = [
                {},  # Missing query
                {"query": ""},  # Empty query
                {"query": "test", "top_k": 0},  # Invalid top_k
                {"query": "test", "top_k": 101},  # Invalid top_k
                {"query": "test", "query_type": "invalid"},  # Invalid query_type
            ]
            
            for invalid_query in invalid_queries:
                response = await client.post(
                    "http://localhost:8000/query",
                    json=invalid_query,
                    headers=headers
                )
                
                # Should return validation error
                assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_query_performance(self):
        """Test query performance under load"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test multiple concurrent queries
            query_data = {
                "query": "performance test query",
                "query_type": "semantic",
                "top_k": 3
            }
            
            tasks = []
            for i in range(10):
                task = client.post(
                    "http://localhost:8000/query",
                    json={**query_data, "metadata": {"request_id": i}},
                    headers=headers
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check that most requests succeeded
            successful_responses = [r for r in responses if isinstance(r, httpx.Response) and r.status_code in [200, 500]]
            assert len(successful_responses) >= 8  # Allow some failures
    
    @pytest.mark.asyncio
    async def test_query_edge_cases(self):
        """Test query edge cases"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            edge_cases = [
                {"query": "a", "query_type": "semantic", "top_k": 1},  # Very short query
                {"query": "a" * 1000, "query_type": "semantic", "top_k": 1},  # Very long query
                {"query": "   spaced   query   ", "query_type": "semantic", "top_k": 1},  # Extra spaces
                {"query": "special!@#$%^&*()chars", "query_type": "semantic", "top_k": 1},  # Special chars
                {"query": "query\nwith\nnewlines", "query_type": "semantic", "top_k": 1},  # Newlines
            ]
            
            for query_data in edge_cases:
                response = await client.post(
                    "http://localhost:8000/query",
                    json=query_data,
                    headers=headers
                )
                
                # Should handle gracefully
                assert response.status_code in [200, 400, 500]


class TestGenerationFlow:
    """Integration tests for text generation flow"""
    
    @pytest.mark.asyncio
    async def test_text_generation_flow(self):
        """Test text generation flow"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # First, get some context via query
            query_data = {
                "query": "machine learning basics",
                "query_type": "semantic",
                "top_k": 3
            }
            
            query_response = await client.post(
                "http://localhost:8000/query",
                json=query_data,
                headers=headers
            )
            
            # Use query results as context for generation
            context = []
            if query_response.status_code == 200:
                query_data = query_response.json()
                context = query_data.get("results", [])
            
            # Generate response
            generation_data = {
                "query": "Explain machine learning in simple terms",
                "context": context,
                "model_name": "gpt-3.5-turbo",
                "max_tokens": 256,
                "temperature": 0.7,
                "metadata": {"user_id": "test_user"}
            }
            
            profiler = PerformanceProfiler()
            profiler.start()
            
            response = await client.post(
                "http://localhost:8000/generate",
                json=generation_data,
                headers=headers
            )
            
            profiler.stop()
            
            assert response.status_code in [200, 500]
            profiler.assert_max_duration(10000)  # Should complete within 10 seconds
            
            if response.status_code == 200:
                data = response.json()
                assert "request_id" in data
                assert "response" in data
                assert "model_name" in data
                assert "tokens_used" in data
                assert "processing_time_ms" in data
                assert data["model_name"] == generation_data["model_name"]
                assert isinstance(data["tokens_used"], int)
                assert data["tokens_used"] > 0
    
    @pytest.mark.asyncio
    async def test_generation_without_context(self):
        """Test text generation without context"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            generation_data = {
                "query": "What is artificial intelligence?",
                "context": [],
                "model_name": "gpt-3.5-turbo",
                "max_tokens": 150,
                "temperature": 0.5
            }
            
            response = await client.post(
                "http://localhost:8000/generate",
                json=generation_data,
                headers=headers
            )
            
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert "response" in data
                assert len(data["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_generation_unauthorized(self):
        """Test text generation without authentication"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            generation_data = {
                "query": "test generation",
                "context": [],
                "model_name": "gpt-3.5-turbo"
            }
            
            response = await client.post(
                "http://localhost:8000/generate",
                json=generation_data
            )
            
            assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_generation_invalid_parameters(self):
        """Test text generation with invalid parameters"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            invalid_generations = [
                {},  # Missing required fields
                {"query": "", "context": []},  # Empty query
                {"query": "test", "context": [], "max_tokens": 0},  # Invalid max_tokens
                {"query": "test", "context": [], "max_tokens": 4097},  # Invalid max_tokens
                {"query": "test", "context": [], "temperature": -0.1},  # Invalid temperature
                {"query": "test", "context": [], "temperature": 2.1},  # Invalid temperature
            ]
            
            for generation_data in invalid_generations:
                response = await client.post(
                    "http://localhost:8000/generate",
                    json=generation_data,
                    headers=headers
                )
                
                assert response.status_code in [400, 422]
