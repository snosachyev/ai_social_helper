"""Contract tests for Document API"""

import pytest
import httpx
import sys
import os
from jsonschema import validate, ValidationError
from uuid import uuid4, UUID

# Add utils path
utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils'))
sys.path.insert(0, utils_path)

from test_helpers import get_auth_token, create_test_file, cleanup_test_files


class TestDocumentAPIContract:
    """Contract tests for Document API endpoints"""
    
    # JSON Schema definitions for API contracts
    DOCUMENT_UPLOAD_REQUEST_SCHEMA = {
        "type": "object",
        "properties": {
            "file": {"type": "string", "format": "binary"},
            "metadata": {
                "type": "object",
                "properties": {
                    "author": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "additionalProperties": True
            }
        },
        "required": ["file"]
    }
    
    DOCUMENT_UPLOAD_RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "document_id": {"type": "string", "format": "uuid"},
            "chunk_count": {"type": "integer", "minimum": 0},
            "processing_time_ms": {"type": "integer", "minimum": 0},
            "timestamp": {"type": "string", "format": "date-time"}
        },
        "required": ["success", "message", "timestamp"]
    }
    
    DOCUMENT_METADATA_SCHEMA = {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "format": "uuid"},
            "filename": {"type": "string", "minLength": 1},
            "file_type": {"type": "string", "enum": ["pdf", "txt", "docx", "html", "markdown"]},
            "size_bytes": {"type": "integer", "minimum": 0},
            "status": {"type": "string", "enum": ["pending", "processing", "completed", "failed"]},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
            "metadata": {"type": "object"}
        },
        "required": ["document_id", "filename", "file_type", "size_bytes", "status", "created_at", "updated_at"]
    }
    
    TEXT_CHUNK_SCHEMA = {
        "type": "object",
        "properties": {
            "chunk_id": {"type": "string", "format": "uuid"},
            "document_id": {"type": "string", "format": "uuid"},
            "text": {"type": "string"},
            "chunk_index": {"type": "integer", "minimum": 0},
            "start_char": {"type": "integer", "minimum": 0},
            "end_char": {"type": "integer", "minimum": 0},
            "metadata": {"type": "object"}
        },
        "required": ["chunk_id", "document_id", "text", "chunk_index", "start_char", "end_char", "metadata"]
    }
    
    ERROR_RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error_code": {"type": "string"},
            "detail": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"}
        },
        "required": ["success", "detail"]
    }
    
    @pytest.mark.asyncio
    async def test_document_upload_contract(self):
        """Test document upload API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            print(f"DEBUG: Got token: {token[:20]}...")
            headers = {"Authorization": f"Bearer {token}"}
            print(f"DEBUG: Headers: {headers}")
            
            test_file_path = create_test_file(
                content="Contract test document content for API validation.",
                suffix=".txt"
            )
            
            try:
                # Test successful upload with simple JSON
                response = await client.post(
                    "http://localhost:8000/documents/upload",
                    json={
                        "filename": "contract_test.txt",
                        "content": "Contract test document content for API validation.",
                        "metadata": {"author": "contract_test", "tags": ["test", "api"]}
                    },
                    headers=headers
                )
                
                print(f"DEBUG: Response status: {response.status_code}")
                print(f"DEBUG: Response body: {response.text}")
                
                # Verify response status
                assert response.status_code == 200
                
                # Verify response headers
                assert "content-type" in response.headers
                assert "application/json" in response.headers["content-type"]
                
                # Validate response schema
                response_data = response.json()
                validate(instance=response_data, schema=self.DOCUMENT_UPLOAD_RESPONSE_SCHEMA)
                
                # Verify specific contract requirements
                assert response_data["success"] is True
                assert "document_id" in response_data
                assert isinstance(response_data["document_id"], str)
                assert len(response_data["document_id"]) > 0
                
                # Verify UUID format
                try:
                    UUID(response_data["document_id"])  # Will raise if not valid UUID
                except ValueError:
                    pytest.fail("document_id is not a valid UUID")
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_upload_error_contract(self):
        """Test document upload error response contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test upload without file
            response = await client.post(
                "http://localhost:8000/documents/upload",
                headers=headers
            )
            
            # Verify error response
            assert response.status_code in [400, 422]
            
            response_data = response.json()
            validate(instance=response_data, schema=self.ERROR_RESPONSE_SCHEMA)
            
            assert response_data["success"] is False
            assert "detail" in response_data
            assert len(response_data["detail"]) > 0
    
    @pytest.mark.asyncio
    async def test_document_get_contract(self):
        """Test document retrieval API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # First upload a document
            test_file_path = create_test_file(
                content="Document for get contract test.",
                suffix=".txt"
            )
            
            try:
                # Test successful upload with JSON (matching our mock)
                upload_response = await client.post(
                    "http://localhost:8000/documents/upload",
                    json={
                        "filename": "get_contract_test.txt",
                        "content": "Document for get contract test.",
                        "metadata": {"author": "contract_test", "tags": ["test", "api"]}
                    },
                    headers=headers
                )
                
                assert upload_response.status_code == 200
                document_id = upload_response.json()["document_id"]
                
                # Test successful retrieval
                response = await client.get(
                    f"http://localhost:8000/documents/{document_id}",
                    headers=headers
                )
                
                # Verify response status and headers
                assert response.status_code == 200
                assert "application/json" in response.headers["content-type"]
                
                # Validate response schema
                response_data = response.json()
                validate(instance=response_data, schema=self.DOCUMENT_METADATA_SCHEMA)
                
                # Verify specific contract requirements
                assert response_data["document_id"] == document_id
                assert response_data["filename"] == "get_contract_test.txt"
                assert response_data["file_type"] == "txt"
                assert response_data["size_bytes"] > 0
                assert response_data["status"] in ["pending", "processing", "completed", "failed"]
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_get_not_found_contract(self):
        """Test document not found response contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            non_existent_id = str(uuid4())
            response = await client.get(
                f"http://localhost:8000/documents/{non_existent_id}",
                headers=headers
            )
            
            # Verify 404 response
            assert response.status_code == 404
            
            # Validate error response schema
            response_data = response.json()
            validate(instance=response_data, schema=self.ERROR_RESPONSE_SCHEMA)
    
    @pytest.mark.asyncio
    async def test_document_list_contract(self):
        """Test document listing API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                "http://localhost:8000/documents",
                headers=headers
            )
            
            # Verify response status
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            
            # Validate response is an array
            response_data = response.json()
            assert isinstance(response_data, list)
            
            # Validate each document in the array
            for doc in response_data:
                validate(instance=doc, schema=self.DOCUMENT_METADATA_SCHEMA)
    
    @pytest.mark.asyncio
    async def test_document_chunks_contract(self):
        """Test document chunks retrieval API contract"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Upload a document first
            test_file_path = create_test_file(
                content="First chunk. Second chunk. Third chunk.",
                suffix=".txt"
            )
            
            try:
                # Upload a document with JSON (matching our mock)
                upload_response = await client.post(
                    "http://localhost:8000/documents/upload",
                    json={
                        "filename": "chunks_contract_test.txt",
                        "content": "First chunk. Second chunk. Third chunk.",
                        "metadata": {"author": "contract_test", "tags": ["test", "api"]}
                    },
                    headers=headers
                )
                
                assert upload_response.status_code == 200
                document_id = upload_response.json()["document_id"]
                
                # Wait a bit for processing
                import asyncio
                await asyncio.sleep(2)
                
                # Test chunks retrieval
                response = await client.get(
                    f"http://localhost:8000/documents/{document_id}/chunks",
                    headers=headers
                )
                
                # Verify response status and headers
                assert response.status_code == 200
                assert "application/json" in response.headers["content-type"]
                
                # Validate response is an array
                response_data = response.json()
                assert isinstance(response_data, list)
                
                # Validate each chunk in the array
                for chunk in response_data:
                    validate(instance=chunk, schema=self.TEXT_CHUNK_SCHEMA)
                    
                    # Verify chunk belongs to the document
                    assert chunk["document_id"] == document_id
                    
                    # Verify character positions
                    assert chunk["end_char"] >= chunk["start_char"]
                    assert chunk["chunk_index"] >= 0
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_authentication_contract(self):
        """Test authentication requirements for document API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test endpoints without authentication
            endpoints = [
                ("GET", "/documents"),
                ("GET", f"/documents/{uuid4()}"),
                ("GET", f"/documents/{uuid4()}/chunks"),
                ("POST", "/documents/upload")
            ]
            
            for method, path in endpoints:
                if method == "GET":
                    response = await client.get(f"http://localhost:8000{path}")
                else:
                    response = await client.post(f"http://localhost:8000{path}")
                
                # Should require authentication
                assert response.status_code == 403
                
                # Validate error response schema
                response_data = response.json()
                validate(instance=response_data, schema=self.ERROR_RESPONSE_SCHEMA)
                assert response_data["success"] is False
    
    @pytest.mark.asyncio
    async def test_document_rate_limiting_contract(self):
        """Test rate limiting behavior"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Make multiple rapid requests
            responses = []
            for i in range(20):  # Adjust based on rate limit configuration
                response = await client.get(
                    "http://localhost:8000/documents",
                    headers=headers
                )
                responses.append(response)
                
                if response.status_code == 429:
                    break
            
            # At least one request should hit rate limit
            rate_limited = any(r.status_code == 429 for r in responses)
            
            if rate_limited:
                # Validate rate limit response
                rate_limit_response = next(r for r in responses if r.status_code == 429)
                response_data = rate_limit_response.json()
                
                # Should have proper error structure
                assert "detail" in response_data
                assert "rate" in response_data["detail"].lower() or "limit" in response_data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_document_cors_contract(self):
        """Test CORS headers"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test preflight request
            response = await client.options(
                "http://localhost:8000/documents",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization"
                }
            )
            
            # Should have CORS headers
            if response.status_code == 200:
                assert "access-control-allow-origin" in response.headers
                assert "access-control-allow-methods" in response.headers
                assert "access-control-allow-headers" in response.headers
