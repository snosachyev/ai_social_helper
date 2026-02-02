"""
Simple API Gateway for load testing
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import time
import logging
import asyncio
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs
SERVICE_URLS = {
    "document": "http://document-service:8001",
    "embedding": "http://embedding-service:8002", 
    "vector": "http://vector-service:8003",
    "retrieval": "http://retrieval-service:8004",
    "generation": "http://generation-service:8005",
    "model": "http://model-service:8006",
    "knowledge": "http://knowledge-service:8007"
}

security = HTTPBearer()

app = FastAPI(
    title="RAG API Gateway (Load Testing)",
    description="Simple API Gateway for load testing",
    version="1.0.0-test"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple rate limiting for testing
class SimpleRateLimiter:
    def __init__(self, max_requests=1000, window_size=60):
        self.max_requests = max_requests
        self.window_size = window_size
        self.requests = {}
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id] 
            if now - req_time < self.window_size
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True

rate_limiter = SimpleRateLimiter(max_requests=10000)  # High limit for load testing

@app.middleware("http")
async def middleware(request: Request, call_next):
    """Global middleware for load testing."""
    start_time = time.time()
    
    # Skip rate limiting for health endpoint and load testing
    if request.url.path in ["/health", "/metrics"] or request.headers.get("X-Load-Test") == "true":
        # Process request without rate limiting for tests
        response = await call_next(request)
    else:
        # Rate limiting for other requests
        client_id = request.client.host
        if not rate_limiter.is_allowed(client_id):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Rate limit exceeded"}
            )
        
        # Process request
        response = await call_next(request)
    
    # Add timing header
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token - simplified for load testing."""
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    token = credentials.credentials
    
    # Test mode: accept test tokens for load testing
    if token.startswith("test-load-token-"):
        return token
    
    # Accept any non-empty token for testing
    if token and len(token) > 5:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials"
    )

# Health endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint - no auth required."""
    return {
        "success": True,
        "service_name": "api-gateway",
        "status": "healthy",
        "details": {"version": "1.0.0-test"}
    }

@app.get("/metrics")
async def metrics():
    """Simple metrics endpoint."""
    return {"status": "ok", "message": "Load testing metrics"}

# Test endpoints
@app.post("/test-upload")
async def test_upload(request: Request):
    """Test upload endpoint for load testing."""
    try:
        data = await request.json()
        return {
            "success": True,
            "message": "Test upload successful",
            "data": data
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Document service routes
@app.post("/documents/upload")
async def upload_document(request: Request, token: str = Depends(verify_token)):
    """Upload document endpoint."""
    try:
        # Simulate processing
        await asyncio.sleep(0.1)  # Simulate some processing time
        
        return {
            "success": True,
            "document_id": f"doc_{int(time.time())}",
            "message": "Document uploaded successfully"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/documents")
async def list_documents(token: str = Depends(verify_token)):
    """List documents endpoint."""
    try:
        # Simulate database query
        await asyncio.sleep(0.05)
        
        return {
            "success": True,
            "documents": [
                {"id": "doc1", "filename": "test1.pdf"},
                {"id": "doc2", "filename": "test2.pdf"}
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/documents/{document_id}")
async def get_document(document_id: str, token: str = Depends(verify_token)):
    """Get document endpoint."""
    try:
        await asyncio.sleep(0.05)
        
        return {
            "success": True,
            "document": {
                "id": document_id,
                "filename": f"{document_id}.pdf",
                "size": 1024000
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Query endpoints
@app.post("/query")
async def query(request: Request, token: str = Depends(verify_token)):
    """Query endpoint."""
    try:
        data = await request.json()
        query_text = data.get("query", "")
        
        # Simulate RAG processing
        await asyncio.sleep(0.2)  # Simulate processing time
        
        return {
            "success": True,
            "query": query_text,
            "results": [
                {"content": f"Result for: {query_text}", "score": 0.95},
                {"content": "Another result", "score": 0.87}
            ],
            "sources": ["doc1", "doc2"]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/generate")
async def generate(request: Request, token: str = Depends(verify_token)):
    """Generate response endpoint."""
    try:
        data = await request.json()
        
        # Simulate LLM generation
        await asyncio.sleep(0.5)  # Simulate LLM processing
        
        return {
            "success": True,
            "response": f"Generated response for: {data.get('query', '')}",
            "tokens_generated": 150,
            "processing_time": 0.5
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Model management endpoints
@app.get("/models")
async def list_models(token: str = Depends(verify_token)):
    """List available models."""
    try:
        await asyncio.sleep(0.1)
        
        return {
            "success": True,
            "models": [
                {"name": "gpt-3.5-turbo", "status": "ready"},
                {"name": "bert-base", "status": "ready"}
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/models/{model_name}/load")
async def load_model(model_name: str, token: str = Depends(verify_token)):
    """Load model endpoint."""
    try:
        # Simulate model loading
        await asyncio.sleep(1.0)
        
        return {
            "success": True,
            "model": model_name,
            "status": "loaded",
            "load_time": 1.0
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Knowledge base endpoints
@app.get("/knowledge/search")
async def search_knowledge(request: Request, token: str = Depends(verify_token)):
    """Search knowledge base."""
    try:
        await asyncio.sleep(0.15)
        
        return {
            "success": True,
            "results": [
                {"title": "Knowledge item 1", "content": "Content 1"},
                {"title": "Knowledge item 2", "content": "Content 2"}
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
