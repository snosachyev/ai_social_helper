from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG System API Gateway - Simple",
    description="Simple RAG system API Gateway for testing",
    version="1.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "service_name": "api-gateway-simple",
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

@app.get("/metrics")
async def metrics():
    """Simple metrics endpoint."""
    return {
        "status": "ok",
        "message": "Simple metrics - no prometheus"
    }

@app.post("/query")
async def query_endpoint(request: dict):
    """Simple query endpoint for testing."""
    try:
        query_text = request.get("query", "")
        if not query_text:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Mock response for testing
        return {
            "query": query_text,
            "response": f"This is a mock response for: {query_text}",
            "sources": ["mock_source_1", "mock_source_2"],
            "processing_time": 0.1,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def list_documents():
    """Simple documents endpoint."""
    return {
        "documents": [
            {"id": "1", "title": "Test Document 1", "type": "pdf"},
            {"id": "2", "title": "Test Document 2", "type": "txt"}
        ],
        "total": 2,
        "status": "success"
    }

@app.get("/models")
async def list_models():
    """Simple models endpoint."""
    return {
        "models": [
            {"name": "gpt-3.5-turbo", "type": "llm", "status": "available"},
            {"name": "text-embedding-ada-002", "type": "embedding", "status": "available"}
        ],
        "total": 2,
        "status": "success"
    }

@app.post("/documents/upload")
async def upload_document():
    """Simple upload endpoint."""
    return {
        "message": "Document upload endpoint - mock response",
        "document_id": f"doc_{int(time.time())}",
        "status": "uploaded",
        "processing_time": 0.5
    }

@app.post("/generate")
async def generate_response(request: dict):
    """Simple generate endpoint."""
    try:
        prompt = request.get("prompt", "")
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
        
        # Mock response
        return {
            "prompt": prompt,
            "response": f"This is a mock generated response for: {prompt}",
            "model": "mock-gpt-model",
            "tokens_used": 150,
            "processing_time": 0.8,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )