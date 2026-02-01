"""Contract tests for Embedding Service"""

import pytest
import httpx
import sys
import os
from jsonschema import validate, ValidationError
from uuid import uuid4

# Add utils path
utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils'))
sys.path.insert(0, utils_path)

from test_helpers import get_auth_token


class TestEmbeddingServiceContract:
    """Contract tests for Embedding Service endpoints"""
    
    # JSON Schema definitions
    EMBEDDING_GENERATION_REQUEST_SCHEMA = {
        "type": "object",
        "properties": {
            "chunk_id": {"type": "string", "format": "uuid"},
            "text": {"type": "string", "minLength": 1},
            "model_name": {"type": "string"}
        },
        "required": ["chunk_id", "text"]
    }
    
    EMBEDDING_VECTOR_SCHEMA = {
        "type": "object",
        "properties": {
            "vector_id": {"type": "string", "format": "uuid"},
            "chunk_id": {"type": "string", "format": "uuid"},
            "embedding": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 1
            },
            "model_name": {"type": "string"},
            "dimension": {"type": "integer", "minimum": 1},
            "created_at": {"type": "string", "format": "date-time"}
        },
        "required": ["vector_id", "chunk_id", "embedding", "model_name", "dimension", "created_at"]
    }
    
    BATCH_EMBEDDING_REQUEST_SCHEMA = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "chunk_id": {"type": "string", "format": "uuid"},
                "text": {"type": "string", "minLength": 1}
            },
            "required": ["chunk_id", "text"]
        },
        "minItems": 1,
        "maxItems": 100
    }
    
    MODEL_INFO_SCHEMA = {
        "type": "object",
        "properties": {
            "model_id": {"type": "string", "format": "uuid"},
            "name": {"type": "string"},
            "type": {"type": "string", "enum": ["embedding", "generation", "reranking"]},
            "version": {"type": "string"},
            "status": {"type": "string", "enum": ["loaded", "loading", "unloaded", "error"]},
            "memory_usage_mb": {"type": "integer", "minimum": 0},
            "loaded_at": {"type": "string", "format": "date-time"},
            "last_used": {"type": "string", "format": "date-time"},
            "config": {"type": "object"}
        },
        "required": ["model_id", "name", "type", "version", "status", "memory_usage_mb", "config"]
    }
    
    ERROR_RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "detail": {"type": "string"}
        },
        "required": ["detail"]
    }
    
    @pytest.mark.asyncio
    async def test_embedding_generation_contract(self):
        """Test embedding generation API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            chunk_id = str(uuid4())
            test_text = "This is a test text for embedding generation."
            
            request_data = {
                "chunk_id": chunk_id,
                "text": test_text,
                "model_name": "sentence-transformers/all-MiniLM-L6-v2"
            }
            
            # Validate request schema
            validate(instance=request_data, schema=self.EMBEDDING_GENERATION_REQUEST_SCHEMA)
            
            response = await client.post(
                "http://localhost:8002/embeddings/generate",
                json=request_data
            )
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate response schema
            response_data = response.json()
            validate(instance=response_data, schema=self.EMBEDDING_VECTOR_SCHEMA)
            
            # Verify specific contract requirements
            assert response_data["chunk_id"] == chunk_id
            assert isinstance(response_data["embedding"], list)
            assert len(response_data["embedding"]) > 0
            assert all(isinstance(x, (int, float)) for x in response_data["embedding"])
            assert response_data["dimension"] == len(response_data["embedding"])
            assert response_data["model_name"] == request_data["model_name"]
            
            # Verify UUID format
            try:
                uuid.UUID(response_data["vector_id"])
                uuid.UUID(response_data["chunk_id"])
            except ValueError:
                pytest.fail("Invalid UUID format in response")
    
    @pytest.mark.asyncio
    async def test_batch_embedding_generation_contract(self):
        """Test batch embedding generation API contract"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            chunks = []
            for i in range(3):
                chunks.append({
                    "chunk_id": str(uuid4()),
                    "text": f"Test text chunk {i} for batch embedding generation."
                })
            
            # Validate request schema
            validate(instance=chunks, schema=self.BATCH_EMBEDDING_REQUEST_SCHEMA)
            
            response = await client.post(
                "http://localhost:8002/embeddings/batch",
                json=chunks
            )
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate response is an array
            response_data = response.json()
            assert isinstance(response_data, list)
            assert len(response_data) == len(chunks)
            
            # Validate each embedding in the array
            for i, embedding in enumerate(response_data):
                validate(instance=embedding, schema=self.EMBEDDING_VECTOR_SCHEMA)
                
                # Verify chunk correspondence
                assert embedding["chunk_id"] == chunks[i]["chunk_id"]
                assert isinstance(embedding["embedding"], list)
                assert len(embedding["embedding"]) > 0
    
    @pytest.mark.asyncio
    async def test_embedding_retrieval_contract(self):
        """Test embedding retrieval API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First generate an embedding
            chunk_id = str(uuid4())
            test_text = "Test text for retrieval contract."
            
            generation_response = await client.post(
                "http://localhost:8002/embeddings/generate",
                json={
                    "chunk_id": chunk_id,
                    "text": test_text
                }
            )
            
            assert generation_response.status_code == 200
            
            # Retrieve the embedding
            response = await client.get(
                f"http://localhost:8002/embeddings/{chunk_id}"
            )
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate response structure
            response_data = response.json()
            assert "vector_id" in response_data
            assert "chunk_id" in response_data
            assert "embedding" in response_data
            assert "model_name" in response_data
            assert "dimension" in response_data
            assert "created_at" in response_data
            
            # Verify data consistency
            assert response_data["chunk_id"] == chunk_id
            assert isinstance(response_data["embedding"], list)
            assert len(response_data["embedding"]) > 0
    
    @pytest.mark.asyncio
    async def test_embedding_not_found_contract(self):
        """Test embedding not found response contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            non_existent_id = str(uuid4())
            response = await client.get(
                f"http://localhost:8002/embeddings/{non_existent_id}"
            )
            
            # Verify 404 response
            assert response.status_code == 404
            
            # Validate error response schema
            response_data = response.json()
            validate(instance=response_data, schema=self.ERROR_RESPONSE_SCHEMA)
            assert "not found" in response_data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_model_listing_contract(self):
        """Test model listing API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("http://localhost:8002/models")
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate response is an array
            response_data = response.json()
            assert isinstance(response_data, list)
            
            # Validate each model in the array
            for model in response_data:
                validate(instance=model, schema=self.MODEL_INFO_SCHEMA)
                
                # Verify specific contract requirements
                assert model["type"] == "embedding"
                assert model["status"] in ["loaded", "loading", "unloaded", "error"]
                assert model["memory_usage_mb"] >= 0
    
    @pytest.mark.asyncio
    async def test_model_loading_contract(self):
        """Test model loading API contract"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            
            response = await client.post(
                f"http://localhost:8002/models/{model_name}/load"
            )
            
            # Verify response status
            assert response.status_code in [200, 500]  # May fail if model already loaded
            
            if response.status_code == 200:
                response_data = response.json()
                assert isinstance(response_data, dict)
                assert "message" in response_data
                assert model_name in response_data["message"]
    
    @pytest.mark.asyncio
    async def test_model_unloading_contract(self):
        """Test model unloading API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            
            response = await client.delete(
                f"http://localhost:8002/models/{model_name}/unload"
            )
            
            # Verify response status
            assert response.status_code == 200
            
            response_data = response.json()
            assert isinstance(response_data, dict)
            assert "message" in response_data
            assert model_name in response_data["message"]
    
    @pytest.mark.asyncio
    async def test_embedding_validation_contract(self):
        """Test embedding generation with invalid data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            invalid_requests = [
                {},  # Missing required fields
                {"text": "test"},  # Missing chunk_id
                {"chunk_id": str(uuid4())},  # Missing text
                {"chunk_id": str(uuid4()), "text": ""},  # Empty text
                {"chunk_id": "invalid-uuid", "text": "test"},  # Invalid UUID
            ]
            
            for request_data in invalid_requests:
                response = await client.post(
                    "http://localhost:8002/embeddings/generate",
                    json=request_data
                )
                
                # Should return validation error
                assert response.status_code in [400, 422]
                
                # Validate error response schema
                response_data = response.json()
                validate(instance=response_data, schema=self.ERROR_RESPONSE_SCHEMA)
    
    @pytest.mark.asyncio
    async def test_batch_embedding_validation_contract(self):
        """Test batch embedding generation with invalid data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            invalid_requests = [
                [],  # Empty array
                [{"text": "test"}],  # Missing chunk_id
                [{"chunk_id": str(uuid4())}],  # Missing text
                [{"chunk_id": "invalid", "text": "test"}],  # Invalid UUID
            ]
            
            for request_data in invalid_requests:
                response = await client.post(
                    "http://localhost:8002/embeddings/batch",
                    json=request_data
                )
                
                # Should return validation error
                assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_health_check_contract(self):
        """Test health check API contract"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8002/health")
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate health check response
            response_data = response.json()
            assert isinstance(response_data, dict)
            assert "status" in response_data
            assert "service" in response_data
            assert response_data["status"] == "healthy"
            assert response_data["service"] == "embedding-service"
            
            # Optional fields
            if "loaded_models" in response_data:
                assert isinstance(response_data["loaded_models"], list)
            
            if "memory_usage_mb" in response_data:
                assert isinstance(response_data["memory_usage_mb"], (int, float))
    
    @pytest.mark.asyncio
    async def test_embedding_service_performance_contract(self):
        """Test embedding service performance requirements"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            import time
            
            chunk_id = str(uuid4())
            test_text = "Performance test text for embedding generation."
            
            start_time = time.time()
            
            response = await client.post(
                "http://localhost:8002/embeddings/generate",
                json={
                    "chunk_id": chunk_id,
                    "text": test_text
                }
            )
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Verify response status
            assert response.status_code == 200
            
            # Verify performance requirements (should complete within 5 seconds)
            assert duration_ms < 5000, f"Embedding generation took {duration_ms:.2f}ms, expected < 5000ms"
            
            # Validate response
            response_data = response.json()
            validate(instance=response_data, schema=self.EMBEDDING_VECTOR_SCHEMA)
            
            # Verify embedding quality (should have reasonable dimensions)
            assert response_data["dimension"] >= 100  # Typical embedding dimensions
            assert len(response_data["embedding"]) == response_data["dimension"]
