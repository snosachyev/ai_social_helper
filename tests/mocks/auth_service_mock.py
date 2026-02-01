#!/usr/bin/env python3
"""Advanced mock Auth service for testing"""

import json
import uuid
import jwt
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import sys
import os

class MockAuthServiceHandler(http.server.SimpleHTTPRequestHandler):
    """Advanced mock Auth service handler"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.users = {
            "test@example.com": {
                "user_id": str(uuid.uuid4()),
                "email": "test@example.com",
                "password": "test",
                "created_at": datetime.utcnow().isoformat()
            }
        }
        self.blacklisted_tokens = set()
        self.jwt_secret = "test_secret_key_for_testing_only"
        
    def do_GET(self):
        """Handle GET requests"""
        path = self.path
        
        if path == '/health':
            self._send_json(200, {
                "status": "healthy",
                "service": "auth-service",
                "version": "1.0.0"
            })
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        path = self.path
        
        if path == '/auth/login':
            self._handle_auth_login()
        elif path == '/auth/logout':
            self._handle_auth_logout()
        elif path == '/auth/refresh':
            self._handle_auth_refresh()
        elif path == '/auth/validate':
            self._handle_auth_validate()
        else:
            self._send_error(404, {"detail": "Not found"})
    
    def _handle_auth_login(self):
        """Handle authentication login"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No credentials provided"})
            return
        
        try:
            # Read request body
            content_length = int(self.headers['content-length'])
            post_data = self.rfile.read(content_length)
            
            # Parse JSON (simplified)
            try:
                import json
                request_data = json.loads(post_data.decode('utf-8'))
            except:
                self._send_error(400, {"detail": "Invalid JSON"})
                return
            
            email = request_data.get('email')
            password = request_data.get('password')
            
            if not email or not password:
                self._send_error(400, {"detail": "Email and password required"})
                return
            
            # Validate credentials
            users = {
                "test@example.com": {
                    "user_id": str(uuid.uuid4()),
                    "email": "test@example.com",
                    "password": "test",
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            user = users.get(email)
            if not user or user['password'] != password:
                self._send_error(401, {"detail": "Invalid credentials"})
                return
            
            # Generate JWT token
            jwt_secret = "test_secret_key_for_testing_only"
            token_payload = {
                'user_id': user['user_id'],
                'email': user['email'],
                'exp': datetime.utcnow() + timedelta(hours=1),
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(token_payload, jwt_secret, algorithm='HS256')
            
            response = {
                'access_token': token,
                'token_type': 'bearer',
                'expires_in': 3600,
                'user_id': user['user_id'],
                'email': user['email']
            }
            
            self._send_json(200, response)
            
        except Exception as e:
            self._send_error(500, {"detail": f"Internal server error: {str(e)}"})
    
    def _handle_auth_logout(self):
        """Handle authentication logout"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No token provided"})
            return
        
        try:
            # Read request body
            content_length = int(self.headers['content-length'])
            post_data = self.rfile.read(content_length)
            
            import json
            request_data = json.loads(post_data.decode('utf-8'))
            
            token = request_data.get('token')
            if not token:
                self._send_error(400, {"detail": "Token required"})
                return
            
            # Add token to blacklist
            self.blacklisted_tokens.add(token)
            
            self._send_json(200, {
                'message': 'Logout successful',
                'token': token[:20] + '...'  # Show partial token for security
            })
            
        except Exception as e:
            self._send_error(500, {"detail": f"Internal server error: {str(e)}"})
    
    def _handle_auth_refresh(self):
        """Handle token refresh"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No token provided"})
            return
        
        try:
            # Read request body
            content_length = int(self.headers['content-length'])
            post_data = self.rfile.read(content_length)
            
            import json
            request_data = json.loads(post_data.decode('utf-8'))
            
            token = request_data.get('token')
            if not token:
                self._send_error(400, {"detail": "Token required"})
                return
            
            # Validate token
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
                user_id = payload['user_id']
                email = payload['email']
                
                # Generate new token
                new_token_payload = {
                    'user_id': user_id,
                    'email': email,
                    'exp': datetime.utcnow() + timedelta(hours=1),
                    'iat': datetime.utcnow()
                }
                
                new_token = jwt.encode(new_token_payload, self.jwt_secret, algorithm='HS256')
                
                self._send_json(200, {
                    'access_token': new_token,
                    'token_type': 'bearer',
                    'expires_in': 3600,
                    'user_id': user_id,
                    'email': email
                })
                
            except jwt.ExpiredSignatureError:
                self._send_error(401, {"detail": "Token expired"})
            except jwt.InvalidTokenError:
                self._send_error(401, {"detail": "Invalid token"})
            
        except Exception as e:
            self._send_error(500, {"detail": f"Internal server error: {str(e)}"})
    
    def _handle_auth_validate(self):
        """Handle token validation"""
        content_length = int(self.headers.get('content-length', 0))
        
        if content_length == 0:
            self._send_error(400, {"detail": "No token provided"})
            return
        
        try:
            # Read request body
            content_length = int(self.headers['content-length'])
            post_data = self.rfile.read(content_length)
            
            import json
            request_data = json.loads(post_data.decode('utf-8'))
            
            token = request_data.get('token')
            if not token:
                self._send_error(400, {"detail": "Token required"})
                return
            
            # Check if token is blacklisted
            if token in self.blacklisted_tokens:
                self._send_error(401, {"detail": "Token has been revoked"})
                return
            
            # Validate token
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
                
                self._send_json(200, {
                    'valid': True,
                    'user_id': payload['user_id'],
                    'email': payload['email'],
                    'exp': payload['exp']
                })
                
            except jwt.ExpiredSignatureError:
                self._send_error(401, {"detail": "Token expired"})
            except jwt.InvalidTokenError:
                self._send_error(401, {"detail": "Invalid token"})
            
        except Exception as e:
            self._send_error(500, {"detail": f"Internal server error: {str(e)}"})
    
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
    """Run the mock Auth service server"""
    port = 8007
    
    with socketserver.TCPServer(('', port), MockAuthServiceHandler) as httpd:
        print(f"🚀 Mock Auth Service running on port {port}")
        print(f"📋 Available endpoints:")
        print(f"   GET  http://localhost:{port}/health")
        print(f"   POST http://localhost:{port}/auth/login")
        print(f"   POST http://localhost:{port}/auth/logout")
        print(f"   POST http://localhost:{port}/auth/refresh")
        print(f"   POST http://localhost:{port}/auth/validate")
        print(f"👤 Test credentials: test@example.com / test")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
