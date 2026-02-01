#!/usr/bin/env python3
"""Advanced mock Embedding service for testing"""

import json
import uuid
import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import sys
import os

class MockEmbeddingServiceHandler(http.server.SimpleHTTPRequestHandler):
    """Advanced mock Embedding service handler"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embeddings = {}  # Mock embedding storage
        self.models = {
            "sentence-transformers/all-MiniLM-L6-v2": {
                "model_id": str(uuid.uuid4()),
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "type": "embedding",
                "version": "2.2-2.0",
                "status": "loaded",
                "memory_usage_mb": 500,
                "loaded_at": datetime.utcnow().isoformat(),
                "last_used": datetime.utcnow().isoformat(),
                "config": {"dimension": 384, "max_length": 512}
            }
        }
        
    def do_GET(self):
        """Handle GET requests"""
        path = self.path
        
        # Route requests
        if path == '/health':
            self._send_json(200, {
                "status": "healthy",
                "service": "embedding-service",
                "version": "1.0.0",
                "loaded_models": ["sentence-transformers/all-MiniLM-L6-v2"]
            })
        elif path == '/models':
            models = {
                "sentence-transformers/all-MiniLM-L6-v2": {
                    "model_id": str(uuid.uuid4()),
                    "name": "sentence-transformers/all-MiniLM-L6-v2",
                    "type": "embedding",
                    "version": "2.2-2.0",
                    "status": "loaded",
                    "memory_usage_mb": 500,
                    "loaded_at": datetime.utcnow().isoformat(),
                    "last_used": datetime.utcnow().isoformat(),
                    "config": {"dimension": 384, "max_length": 512}
                }
            }
            self._send_json(200, list(models.values()))
        elif path.startswith('/embeddings/'):
            self._handle_embedding_get(path)
        elif path.startswith('/models/'):
            self._handle_model_get(path)
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        path = self.path
        
        # Route requests
        if path == '/embeddings/generate':
            self._handle_embedding_generate()
        elif path == '/embeddings/batch':
            self._handle_embedding_batch()
        elif path.startswith('/models/') and path.endswith('/load'):
            self._handle_model_load(path)
        elif path.startswith('/models/') and path.endswith('/unload'):
            self._handle_model_unload(path)
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def _handle_embedding_get(self, path):
        """Handle embedding retrieval"""
        chunk_id = path.split('/')[-1]
        
        if chunk_id in self.embeddings:
            self._send_json(200, self.embeddings[chunk_id])
        else:
            self._send_error(404, {"detail": f"Embedding not found for chunk: {chunk_id}"})
    
    def _handle_model_get(self, path):
        """Handle model info retrieval"""
        model_name = path.split('/')[-2]  # Extract model name
        
        if model_name in self.models:
            self._send_json(200, self.models[model_name])
        else:
            self._send_error(404, {"detail": f"Model not found: {model_name}"})
    
    def _handle_embedding_generate(self):
        """Handle single embedding generation"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No request data provided"})
            return
        
        # Mock embedding generation
        chunk_id = str(uuid.uuid4())
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        dimension = 384
        
        # Generate mock embedding
        embedding = [round(random.uniform(-1, 1), 6) for _ in range(dimension)]
        
        # Create response
        response = {
            "vector_id": str(uuid.uuid4()),
            "chunk_id": chunk_id,
            "embedding": embedding,
            "model_name": model_name,
            "dimension": dimension,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.embeddings[chunk_id] = response
        self._send_json(200, response)
    
    def _handle_embedding_batch(self):
        """Handle batch embedding generation"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No request data provided"})
            return
        
        # Mock batch embedding generation
        responses = []
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        dimension = 384
        
        # Generate mock embeddings for multiple chunks
        for i in range(3):  # Mock 3 chunks
            chunk_id = str(uuid.uuid4())
            embedding = [round(random.uniform(-1, 1), 6) for _ in range(dimension)]
            
            response = {
                "vector_id": str(uuid.uuid4()),
                "chunk_id": chunk_id,
                "embedding": embedding,
                "model_name": model_name,
                "dimension": dimension,
                "created_at": datetime.utcnow().isoformat()
            }
            
            responses.append(response)
            self.embeddings[chunk_id] = response
        
        self._send_json(200, responses)
    
    def _handle_model_load(self):
        """Handle model loading"""
        model_name = path.split('/')[-2]
        
        if model_name not in self.models:
            # Create new model
            self.models[model_name] = {
                "model_id": str(uuid.uuid4()),
                "name": model_name,
                "type": "embedding",
                "version": "1.0.0",
                "status": "loaded",
                "memory_usage_mb": random.randint(300, 800),
                "loaded_at": datetime.utcnow().isoformat(),
                "last_used": datetime.utcnow().isoformat(),
                "config": {"dimension": 384, "max_length": 512}
            }
        
        self._send_json(200, {
            "message": f"Model {model_name} loaded successfully",
            "model_id": self.models[model_name]["model_id"]
        })
    
    def _handle_model_unload(self):
        """Handle model unloading"""
        model_name = path.split('/')[-2]
        
        if model_name in self.models:
            del self.models[model_name]
            self._send_json(200, {
                "message": f"Model {model_name} unloaded successfully"
            })
        else:
            self._send_error(404, {"detail": f"Model not found: {model_name}"})
    
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

def run_server():
    """Run the mock Embedding service server"""
    port = 8002
    
    # Define models directly
    models = {
        "sentence-transformers/all-MiniLM-L6-v2": {
            "model_id": str(uuid.uuid4()),
            "name": "sentence-transformers/all-MiniLM-L6-v2",
            "type": "embedding",
            "version": "2.2-2.0",
            "status": "loaded",
            "memory_usage_mb": 500,
            "loaded_at": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat(),
            "config": {"dimension": 384, "max_length": 512}
        }
    }
    
    with socketserver.TCPServer(('', port), MockEmbeddingServiceHandler) as httpd:
        print(f"🚀 Mock Embedding Service running on port {port}")
        print(f"📋 Available endpoints:")
        print(f"   GET  http://localhost:{port}/health")
        print(f"   GET  http://localhost:{port}/models")
        print(f"   POST http://localhost:{port}/embeddings/generate")
        print(f"   POST http://localhost:{port}/embeddings/batch")
        print(f"   GET  http://localhost:{port}/embeddings/{{chunk_id}}")
        print(f"   POST http://localhost:{port}/models/{{model_name}}/load")
        print(f"   DELETE http://localhost:{port}/models/{{model_name}}/unload")
        print(f"🤖 Available models: {list(models.keys())}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
