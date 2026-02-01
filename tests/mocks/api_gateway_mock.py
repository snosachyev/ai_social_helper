#!/usr/bin/env python3
"""Advanced mock API Gateway service for testing"""

import json
import uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import sys
import os

# Global storage for documents (shared across all handler instances)
DOCUMENTS_STORAGE = {}

class MockAPIGatewayHandler(http.server.SimpleHTTPRequestHandler):
    """Advanced mock API Gateway handler"""
    
    def setup(self):
        """Setup method called after __init__"""
        super().setup()
        # Use global storage
        self.documents = DOCUMENTS_STORAGE
        self.auth_tokens = {"mock-jwt-token-12345": {"user_id": "test-user", "email": "test@example.com"}}
        
    def do_GET(self):
        """Handle GET requests"""
        path = self.path
        headers = dict(self.headers)
        
        # Check authentication
        if not self._is_authenticated(headers):
            self._send_error(403, {"detail": "Authentication required"})
            return
        
        # Route requests
        if path == '/health':
            self._send_json(200, {
                "status": "healthy",
                "service": "api-gateway",
                "version": "1.0.0"
            })
        elif path.startswith('/documents'):
            self._handle_documents_get(path)
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        path = self.path
        headers = dict(self.headers)
        
        # Check authentication for protected endpoints
        if path.startswith('/documents/upload'):
            if not self._is_authenticated(headers):
                self._send_error(403, {"detail": "Authentication required"})
                return
        
        # Route requests
        if path == '/documents/upload':
            self._handle_document_upload()
        elif path.startswith('/auth/login'):
            self._handle_auth_login()
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self._send_cors_response()
    
    def _is_authenticated(self, headers):
        """Check if request is authenticated"""
        # For testing, check for proper Authorization header
        auth_header = headers.get('authorization', '')
        if not auth_header:
            auth_header = headers.get('Authorization', '')
        
        print(f"DEBUG: Auth header: {auth_header}")
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer '
            print(f"DEBUG: Token: {token[:20]}...")
            # For testing, accept any token that starts with 'eyJ' (JWT format)
            return token.startswith('eyJ')
        return False
    
    def _handle_documents_get(self, path):
        """Handle document retrieval"""
        if path == '/documents':
            # List documents
            documents_list = list(self.documents.values())
            self._send_json(200, documents_list)
        elif path.startswith('/documents/') and path.count('/') == 2:
            # Get specific document
            doc_id = path.split('/')[-1]
            if doc_id in self.documents:
                self._send_json(200, self.documents[doc_id])
            else:
                self._send_error(404, {"detail": "Document not found"})
        elif path.endswith('/chunks'):
            # Get document chunks
            doc_id = path.split('/')[-2]  # Extract document ID
            if doc_id in self.documents:
                chunks = self._generate_mock_chunks(doc_id)
                self._send_json(200, chunks)
            else:
                self._send_error(404, {"detail": "Document not found"})
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def _handle_document_upload(self):
        """Handle document upload"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No file provided"})
            return
        
        # Read JSON body for filename
        try:
            content_length = int(self.headers['content-length'])
            post_data = self.rfile.read(content_length)
            
            import json
            request_data = json.loads(post_data.decode('utf-8'))
            filename = request_data.get('filename', f"uploaded_document_{uuid.uuid4().hex[:8]}.txt")
        except:
            filename = f"uploaded_document_{uuid.uuid4().hex[:8]}.txt"
        
        # Mock file processing
        doc_id = str(uuid.uuid4())
        
        # Create mock document
        document = {
            "document_id": doc_id,
            "filename": filename,
            "file_type": "txt",
            "size_bytes": content_length,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": {"upload_source": "test"}
        }
        
        self.documents[doc_id] = document
        
        # Create response
        response = {
            "success": True,
            "message": f"Document uploaded and processed successfully. Generated 5 chunks.",
            "document_id": doc_id,
            "chunk_count": 5,
            "processing_time_ms": 1500,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._send_json(200, response)
    
    def _handle_auth_login(self):
        """Handle authentication"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No credentials provided"})
            return
        
        # Mock authentication
        response = {
            "access_token": "mock-jwt-token-12345",
            "token_type": "bearer",
            "expires_in": 3600,
            "user_id": "test-user",
            "email": "test@example.com"
        }
        
        self._send_json(200, response)
    
    def _generate_mock_chunks(self, doc_id):
        """Generate mock chunks for a document"""
        return [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id,
                "text": f"Mock chunk 1 for document {doc_id}",
                "chunk_index": 0,
                "start_char": 0,
                "end_char": 50,
                "metadata": {"type": "text"}
            },
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id,
                "text": f"Mock chunk 2 for document {doc_id}",
                "chunk_index": 1,
                "start_char": 51,
                "end_char": 100,
                "metadata": {"type": "text"}
            }
        ]
    
    def _send_json(self, status_code, data):
        """Send JSON response"""
        response_data = json.dumps(data).encode('utf-8')
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data)
    
    def _send_error(self, status_code, error_data):
        """Send error response"""
        self._send_json(status_code, {
            "success": False,
            "error_code": str(status_code),
            "detail": error_data.get("detail", "Unknown error"),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _send_cors_response(self):
        """Send CORS preflight response"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

def run_server():
    """Run the mock API Gateway server"""
    port = 8000
    
    with socketserver.TCPServer(('', port), MockAPIGatewayHandler) as httpd:
        print(f"🚀 Mock API Gateway running on port {port}")
        print(f"📋 Available endpoints:")
        print(f"   GET  http://localhost:{port}/health")
        print(f"   POST http://localhost:{port}/auth/login")
        print(f"   POST http://localhost:{port}/documents/upload")
        print(f"   GET  http://localhost:{port}/documents")
        print(f"   GET  http://localhost:{port}/documents/{{id}}")
        print(f"   GET  http://localhost:{port}/documents/{{id}}/chunks")
        print(f"🔐 Mock token: mock-jwt-token-12345")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
