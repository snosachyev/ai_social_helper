"""Integration tests for document processing flow"""

import pytest
import asyncio
import httpx
from uuid import uuid4
import tempfile
import os
from pathlib import Path

from tests.utils.test_helpers import create_test_file, get_auth_token, cleanup_test_files


class TestDocumentUploadFlow:
    """Integration tests for document upload and processing flow"""
    
    @pytest.mark.asyncio
    async def test_complete_document_processing_flow(self):
        """Test complete document processing flow: upload -> process -> retrieve"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Authenticate
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Step 2: Upload document
            test_file_path = create_test_file(
                content="Machine learning is a subset of artificial intelligence. " +
                       "It focuses on algorithms that can learn from data. " +
                       "Deep learning is a type of machine learning that uses neural networks.",
                suffix=".txt"
            )
            
            try:
                # Upload file
                with open(test_file_path, "rb") as f:
                    upload_response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("test_document.txt", f, "text/plain")},
                        headers=headers
                    )
                
                assert upload_response.status_code == 200
                upload_data = upload_response.json()
                assert upload_data["success"] is True
                assert "document_id" in upload_data
                
                document_id = upload_data["document_id"]
                
                # Step 3: Wait for processing (poll status)
                max_attempts = 30
                for attempt in range(max_attempts):
                    status_response = await client.get(
                        f"http://localhost:8000/documents/{document_id}",
                        headers=headers
                    )
                    
                    if status_response.status_code == 200:
                        doc_data = status_response.json()
                        if doc_data.get("status") == "completed":
                            break
                        elif doc_data.get("status") == "failed":
                            pytest.fail(f"Document processing failed: {doc_data}")
                    
                    await asyncio.sleep(1)
                else:
                    pytest.fail("Document processing timeout")
                
                # Step 4: Retrieve document metadata
                doc_response = await client.get(
                    f"http://localhost:8000/documents/{document_id}",
                    headers=headers
                )
                
                assert doc_response.status_code == 200
                doc_data = doc_response.json()
                assert doc_data["document_id"] == document_id
                assert doc_data["filename"] == "test_document.txt"
                assert doc_data["file_type"] == "txt"
                assert doc_data["status"] == "completed"
                
                # Step 5: Retrieve document chunks
                chunks_response = await client.get(
                    f"http://localhost:8000/documents/{document_id}/chunks",
                    headers=headers
                )
                
                assert chunks_response.status_code == 200
                chunks_data = chunks_response.json()
                assert len(chunks_data) > 0
                
                # Verify chunks contain expected content
                chunk_texts = [chunk["text"] for chunk in chunks_data]
                full_text = " ".join(chunk_texts)
                assert "machine learning" in full_text.lower()
                assert "artificial intelligence" in full_text.lower()
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_upload_different_formats(self):
        """Test document upload with different file formats"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            test_cases = [
                (".txt", "text/plain", "This is a plain text document."),
                (".md", "text/markdown", "# Markdown Document\n\nThis is a **markdown** file."),
            ]
            
            for suffix, content_type, content in test_cases:
                test_file_path = create_test_file(content=content, suffix=suffix)
                
                try:
                    with open(test_file_path, "rb") as f:
                        response = await client.post(
                            "http://localhost:8000/documents/upload",
                            files={"file": (f"test{suffix}", f, content_type)},
                            headers=headers
                        )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "document_id" in data
                    
                finally:
                    cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_upload_unauthorized(self):
        """Test document upload without authentication"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            test_file_path = create_test_file(content="Unauthorized content", suffix=".txt")
            
            try:
                with open(test_file_path, "rb") as f:
                    response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("unauthorized.txt", f, "text/plain")}
                    )
                
                assert response.status_code == 403
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_upload_invalid_file_type(self):
        """Test document upload with invalid file type"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            test_file_path = create_test_file(content="fake exe content", suffix=".exe")
            
            try:
                with open(test_file_path, "rb") as f:
                    response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("malware.exe", f, "application/octet-stream")},
                        headers=headers
                    )
                
                assert response.status_code == 400
                data = response.json()
                assert data["success"] is False
                assert "error" in data.get("detail", "").lower()
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_upload_large_file(self):
        """Test document upload with large file"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Create a large file (5MB)
            large_content = "Large document content. " * 100000  # ~2.5MB
            test_file_path = create_test_file(content=large_content, suffix=".txt")
            
            try:
                with open(test_file_path, "rb") as f:
                    response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("large_document.txt", f, "text/plain")},
                        headers=headers
                    )
                
                # Should either succeed or fail gracefully with size limit error
                if response.status_code == 200:
                    data = response.json()
                    assert data["success"] is True
                elif response.status_code == 400:
                    data = response.json()
                    assert "size" in data.get("detail", "").lower()
                else:
                    pytest.fail(f"Unexpected response status: {response.status_code}")
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_document_retrieval_not_found(self):
        """Test document retrieval for non-existent document"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            non_existent_id = str(uuid4())
            response = await client.get(
                f"http://localhost:8000/documents/{non_existent_id}",
                headers=headers
            )
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_document_listing(self):
        """Test document listing endpoint"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Upload a few documents first
            document_ids = []
            for i in range(3):
                test_file_path = create_test_file(
                    content=f"Test document {i} content.",
                    suffix=".txt"
                )
                
                try:
                    with open(test_file_path, "rb") as f:
                        response = await client.post(
                            "http://localhost:8000/documents/upload",
                            files={"file": (f"test_doc_{i}.txt", f, "text/plain")},
                            headers=headers
                        )
                    
                    if response.status_code == 200:
                        data = response.json()
                        document_ids.append(data["document_id"])
                        
                finally:
                    cleanup_test_files([test_file_path])
            
            # List documents
            response = await client.get(
                "http://localhost:8000/documents",
                headers=headers
            )
            
            assert response.status_code == 200
            documents = response.json()
            assert isinstance(documents, list)
            
            # Should contain at least our uploaded documents
            uploaded_docs = [doc for doc in documents if doc["document_id"] in document_ids]
            assert len(uploaded_docs) == 3
            
            # Test pagination
            response = await client.get(
                "http://localhost:8000/documents?limit=2",
                headers=headers
            )
            
            assert response.status_code == 200
            paginated_docs = response.json()
            assert len(paginated_docs) <= 2
    
    @pytest.mark.asyncio
    async def test_document_chunks_retrieval(self):
        """Test document chunks retrieval"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Upload a document
            test_file_path = create_test_file(
                content="First paragraph. Second paragraph. Third paragraph.",
                suffix=".txt"
            )
            
            try:
                with open(test_file_path, "rb") as f:
                    upload_response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("chunks_test.txt", f, "text/plain")},
                        headers=headers
                    )
                
                assert upload_response.status_code == 200
                document_id = upload_response.json()["document_id"]
                
                # Wait for processing
                await asyncio.sleep(2)
                
                # Get chunks
                chunks_response = await client.get(
                    f"http://localhost:8000/documents/{document_id}/chunks",
                    headers=headers
                )
                
                assert chunks_response.status_code == 200
                chunks = chunks_response.json()
                assert len(chunks) > 0
                
                # Verify chunk structure
                for chunk in chunks:
                    assert "chunk_id" in chunk
                    assert "document_id" in chunk
                    assert "text" in chunk
                    assert "chunk_index" in chunk
                    assert "start_char" in chunk
                    assert "end_char" in chunk
                    assert "metadata" in chunk
                    assert chunk["document_id"] == document_id
                
            finally:
                cleanup_test_files([test_file_path])


class TestDocumentProcessingErrors:
    """Integration tests for document processing error scenarios"""
    
    @pytest.mark.asyncio
    async def test_corrupted_file_upload(self):
        """Test upload of corrupted file"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            # Create corrupted file (invalid UTF-8)
            test_file_path = create_test_file(
                content=b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09',
                suffix=".txt"
            )
            
            try:
                with open(test_file_path, "rb") as f:
                    response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("corrupted.txt", f, "text/plain")},
                        headers=headers
                    )
                
                # Should handle gracefully
                assert response.status_code in [400, 500]
                
            finally:
                cleanup_test_files([test_file_path])
    
    @pytest.mark.asyncio
    async def test_empty_file_upload(self):
        """Test upload of empty file"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            test_file_path = create_test_file(content="", suffix=".txt")
            
            try:
                with open(test_file_path, "rb") as f:
                    response = await client.post(
                        "http://localhost:8000/documents/upload",
                        files={"file": ("empty.txt", f, "text/plain")},
                        headers=headers
                    )
                
                # Should either accept empty files or reject gracefully
                assert response.status_code in [200, 400]
                
            finally:
                cleanup_test_files([test_file_path])
