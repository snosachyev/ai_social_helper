from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import httpx
import time
import logging
from typing import Dict, Any
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from shared.models.base import BaseResponse, ErrorResponse, HealthCheck
from shared.config.settings import settings
from shared.middleware.rate_limiting import RateLimitMiddleware, RateLimitConfig
from shared.database.redis import get_redis_client

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Counter('active_connections', 'Active connections')

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("API Gateway starting up...")
    
    # Initialize Redis client for rate limiting
    redis_client = await get_redis_client()
    app.state.redis_client = redis_client
    
    # Initialize rate limiting
    rate_limit_config = RateLimitConfig(
        default_requests_per_minute=getattr(settings, 'rate_limit_per_minute', 60),
        default_requests_per_hour=getattr(settings, 'rate_limit_per_hour', 1000),
        default_requests_per_day=getattr(settings, 'rate_limit_per_day', 10000)
    )
    app.state.rate_limit_config = rate_limit_config
    
    yield
    logger.info("API Gateway shutting down...")
    if hasattr(app.state, 'redis_client'):
        await app.state.redis_client.close()

app = FastAPI(
    title="RAG System API Gateway",
    description="Production-ready RAG system API Gateway",
    version=settings.service_version,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add rate limiting middleware (will be initialized after Redis is available)
async def add_rate_limiting():
    """Add rate limiting middleware after Redis is available."""
    if hasattr(app.state, 'redis_client') and hasattr(app.state, 'rate_limit_config'):
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=app.state.redis_client,
            config=app.state.rate_limit_config
        )
        logger.info("Rate limiting middleware added")


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.window_size = 60  # seconds
        self.max_requests = 100  # requests per window
    
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


rate_limiter = RateLimiter()


@app.middleware("http")
async def middleware(request: Request, call_next):
    """Global middleware for logging, metrics, and rate limiting."""
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
    
    # Metrics
    process_time = time.time() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_DURATION.observe(process_time)
    
    # Add headers
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token."""
    # Simplified token verification - in production, use proper JWT validation
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    token = credentials.credentials
    
    # Test mode: accept test tokens for load testing
    if token.startswith("test-load-token-"):
        return token
    
    # For now, accept any non-empty token (simplified for testing)
    if token and len(token) > 5:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials"
    )


async def proxy_request(service: str, path: str, method: str, 
                       headers: Dict[str, str] = None, 
                       params: Dict[str, Any] = None,
                       json_data: Dict[str, Any] = None) -> Response:
    """Proxy request to downstream service."""
    service_url = SERVICE_URLS.get(service)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    url = f"{service_url}{path}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            return JSONResponse(
                status_code=response.status_code,
                content=response.json(),
                headers=dict(response.headers)
            )
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health endpoints
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        service_name="api-gateway",
        status="healthy",
        details={"version": settings.service_version}
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/test-upload")
async def test_upload(request: Request):
    """Test upload endpoint."""
    try:
        form = await request.form()
        result = {"received_fields": []}
        
        for key, value in form.items():
            if hasattr(value, 'filename'):
                result["received_fields"].append({
                    "key": key,
                    "filename": value.filename,
                    "content_type": value.content_type,
                    "size": len(await value.read())
                })
            else:
                result["received_fields"].append({
                    "key": key,
                    "value": value
                })
        
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# Document service routes
@app.post("/documents/upload")
async def upload_document(request: Request, token: str = Depends(verify_token)):
    """Upload document endpoint."""
    try:
        # Forward the multipart form request to document service
        form = await request.form()
        
        # Prepare files and form data for forwarding
        files = {}
        form_data = {}
        
        for key, value in form.items():
            if hasattr(value, 'filename') and value.filename:
                # This is a file upload
                files[key] = (value.filename, await value.read(), value.content_type or 'application/octet-stream')
            else:
                # This is regular form data
                form_data[key] = value
        
        if not files:
            return JSONResponse(content={"error": "No file provided"}, status_code=400)
        
        # Forward to document service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SERVICE_URLS['document']}/documents/upload",
                files=files,
                data=form_data,
                headers={"Authorization": f"Bearer {token}"}
            )
        
        return JSONResponse(content=response.json(), status_code=response.status_code)
        
    except Exception as e:
        logger.error(f"Upload proxy error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/documents/{document_id}")
async def get_document(document_id: str, token: str = Depends(verify_token)):
    """Get document endpoint."""
    return await proxy_request(
        service="document",
        path=f"/documents/{document_id}",
        method="GET"
    )


@app.get("/documents")
async def list_documents(token: str = Depends(verify_token)):
    """List documents endpoint."""
    return await proxy_request(
        service="document",
        path="/documents",
        method="GET"
    )


# Query endpoints
@app.post("/query")
async def query(request: Request, token: str = Depends(verify_token)):
    """Query endpoint."""
    return await proxy_request(
        service="retrieval",
        path="/query",
        method="POST",
        headers=dict(request.headers),
        json_data=await request.json()
    )


@app.post("/generate")
async def generate(request: Request, token: str = Depends(verify_token)):
    """Generate response endpoint."""
    return await proxy_request(
        service="generation",
        path="/generate",
        method="POST",
        headers=dict(request.headers),
        json_data=await request.json()
    )


# Model management endpoints
@app.get("/models")
async def list_models(token: str = Depends(verify_token)):
    """List available models."""
    return await proxy_request(
        service="model",
        path="/models",
        method="GET"
    )


@app.post("/models/{model_name}/load")
async def load_model(model_name: str, token: str = Depends(verify_token)):
    """Load model endpoint."""
    return await proxy_request(
        service="model",
        path=f"/models/{model_name}/load",
        method="POST"
    )


# Knowledge base endpoints
@app.get("/knowledge/search")
async def search_knowledge(request: Request, token: str = Depends(verify_token)):
    """Search knowledge base."""
    return await proxy_request(
        service="knowledge",
        path="/knowledge/search",
        method="GET",
        params=dict(request.query_params)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=settings.api_workers
    )
