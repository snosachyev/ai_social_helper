# API Reference Documentation

## Overview

The RAG System provides a comprehensive RESTful API for document processing, querying, and model management. All APIs are accessible through the API Gateway at port 8000, with individual services also accessible directly.

## Authentication

### JWT Token Authentication
All API endpoints (except health checks) require JWT authentication.

```bash
# Get token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'

# Use token
curl -X GET "http://localhost:8000/documents" \
  -H "Authorization: Bearer <your_jwt_token>"
```

## API Gateway Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "service_name": "api-gateway",
  "status": "healthy",
  "timestamp": "2026-01-22T10:31:00Z",
  "details": {
    "version": "1.0.0"
  }
}
```

### Metrics
```http
GET /metrics
```

**Response:** Prometheus metrics format

---

## Document Management API

### Upload Document
```http
POST /documents/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Parameters:**
- `file`: Document file (PDF, TXT, DOCX, HTML, MD)

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded and processed successfully",
  "timestamp": "2026-01-22T10:31:00Z",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "completed",
  "chunk_count": 15,
  "processing_time_ms": 2500
}
```

### Get Document
```http
GET /documents/{document_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_type": "pdf",
  "size_bytes": 1024000,
  "created_at": "2026-01-22T10:31:00Z",
  "updated_at": "2026-01-22T10:31:00Z",
  "status": "completed",
  "metadata": {
    "pages": 10,
    "author": "John Doe"
  },
  "chunks": [
    {
      "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
      "text": "This is the first chunk of text...",
      "chunk_index": 0,
      "start_char": 0,
      "end_char": 1000,
      "metadata": {}
    }
  ]
}
```

### List Documents
```http
GET /documents?skip=0&limit=100&status=completed
Authorization: Bearer <token>
```

**Query Parameters:**
- `skip`: Number of documents to skip (default: 0)
- `limit`: Maximum documents to return (default: 100)
- `status`: Filter by status (optional)

**Response:**
```json
{
  "documents": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "document.pdf",
      "file_type": "pdf",
      "size_bytes": 1024000,
      "status": "completed",
      "created_at": "2026-01-22T10:31:00Z",
      "updated_at": "2026-01-22T10:31:00Z",
      "chunk_count": 15
    }
  ],
  "count": 1,
  "skip": 0,
  "limit": 100
}
```

### Delete Document
```http
DELETE /documents/{document_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Document deleted successfully"
}
```

---

## Query & Retrieval API

### Process Query
```http
POST /query
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "query": "What is machine learning?",
  "query_type": "semantic",
  "top_k": 5,
  "filters": {
    "min_score": 0.5,
    "document_type": "pdf"
  },
  "metadata": {
    "user_id": "user123"
  }
}
```

**Response:**
```json
[
  {
    "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Machine learning is a subset of artificial intelligence...",
    "score": 0.85,
    "metadata": {
      "document_type": "pdf",
      "page": 1
    }
  }
]
```

### Get Query Results
```http
GET /query/{query_id}
Authorization: Bearer <token>
```

**Response:** Same as query response

### Query History
```http
GET /queries/history?skip=0&limit=100
Authorization: Bearer <token>
```

**Response:**
```json
{
  "queries": [
    {
      "query_id": "550e8400-e29b-41d4-a716-446655440002",
      "query_text": "What is machine learning?",
      "query_type": "semantic",
      "results_count": 5,
      "processing_time_ms": 1500,
      "created_at": "2026-01-22T10:31:00Z"
    }
  ]
}
```

### Query Suggestions
```http
POST /query/suggest
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "partial_query": "machine",
  "limit": 5
}
```

**Response:**
```json
{
  "suggestions": [
    {
      "suggestion": "machine learning algorithms",
      "frequency": 10,
      "last_used": "2026-01-22T10:31:00Z"
    }
  ]
}
```

---

## Generation API

### Generate Response
```http
POST /generate
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "query": "Explain the concept of embeddings",
  "context": [
    {
      "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "text": "Embeddings are vector representations of text...",
      "score": 0.85,
      "metadata": {}
    }
  ],
  "model_name": "microsoft/DialoGPT-medium",
  "max_tokens": 512,
  "temperature": 0.7,
  "metadata": {
    "user_id": "user123"
  }
}
```

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440003",
  "response": "Embeddings are numerical vector representations that capture semantic meaning...",
  "model_name": "microsoft/DialoGPT-medium",
  "tokens_used": 150,
  "processing_time_ms": 3000,
  "metadata": {
    "user_id": "user123"
  }
}
```

### Get Generation Result
```http
GET /generation/{request_id}
Authorization: Bearer <token>
```

**Response:** Same as generation response

### Generation History
```http
GET /generation/history?skip=0&limit=100
Authorization: Bearer <token>
```

**Response:**
```json
{
  "generations": [
    {
      "request_id": "550e8400-e29b-41d4-a716-446655440003",
      "query": "Explain the concept of embeddings",
      "model_name": "microsoft/DialoGPT-medium",
      "tokens_used": 150,
      "processing_time_ms": 3000,
      "created_at": "2026-01-22T10:31:00Z"
    }
  ]
}
```

---

## Model Management API

### List Models
```http
GET /models
Authorization: Bearer <token>
```

**Response:**
```json
{
  "models": [
    {
      "model_id": "550e8400-e29b-41d4-a716-446655440004",
      "name": "sentence-transformers/all-MiniLM-L6-v2",
      "type": "embedding",
      "version": "1.0.0",
      "status": "loaded",
      "memory_usage_mb": 500,
      "loaded_at": "2026-01-22T10:31:00Z",
      "last_used": "2026-01-22T10:31:00Z",
      "config": {
        "dimension": 384,
        "request_count": 100
      }
    }
  ]
}
```

### Download Model
```http
POST /models/{model_name}/download
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "model_type": "embedding"
}
```

**Response:**
```json
{
  "message": "Model sentence-transformers/all-MiniLM-L6-v2 downloaded successfully"
}
```

### Load Model
```http
POST /models/{model_name}/load
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Model sentence-transformers/all-MiniLM-L6-v2 loaded successfully"
}
```

### Unload Model
```http
DELETE /models/{model_name}/unload
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Model sentence-transformers/all-MiniLM-L6-v2 unloaded successfully"
}
```

### Delete Model
```http
DELETE /models/{model_name}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Model sentence-transformers/all-MiniLM-L6-v2 deleted successfully"
}
```

---

## Vector Store API

### Add Vectors
```http
POST /vectors/add
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "vectors": [
    {
      "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
      "embedding": [0.1, 0.2, 0.3, ...],
      "model_name": "sentence-transformers/all-MiniLM-L6-v2",
      "dimension": 384
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully added 1 vectors"
}
```

### Search Vectors
```http
POST /vectors/search
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "query_embedding": [0.1, 0.2, 0.3, ...],
  "top_k": 10
}
```

**Response:**
```json
[
  {
    "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Machine learning is a subset of artificial intelligence...",
    "score": 0.85,
    "metadata": {}
  }
]
```

### Vector Statistics
```http
GET /vectors/stats
Authorization: Bearer <token>
```

**Response:**
```json
{
  "type": "chroma",
  "vector_count": 10000,
  "collection_name": "rag_embeddings"
}
```

### Delete Vector
```http
DELETE /vectors/{vector_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Vector 550e8400-e29b-41d4-a716-446655440005 deleted successfully"
}
```

---

## System Management API

### System Resources
```http
GET /system/resources
Authorization: Bearer <token>
```

**Response:**
```json
{
  "memory_total_gb": 32,
  "memory_available_gb": 16,
  "memory_usage_percent": 50,
  "disk_total_gb": 500,
  "disk_available_gb": 300,
  "disk_usage_percent": 40,
  "cpu_usage_percent": 25,
  "cache_directory": "/app/model_cache"
}
```

### Cleanup Old Models
```http
POST /system/cleanup
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "days_old": 30
}
```

**Response:**
```json
{
  "message": "Cleaned up 5 old models"
}
```

---

## Knowledge Base API

### Search Knowledge
```http
GET /knowledge/search?q=machine%20learning&limit=10
Authorization: Bearer <token>
```

**Query Parameters:**
- `q`: Search query
- `limit`: Maximum results (default: 10)
- `filters`: Additional filters (optional)

**Response:**
```json
{
  "results": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Introduction to Machine Learning",
      "snippet": "Machine learning is a subset of artificial intelligence...",
      "score": 0.92,
      "metadata": {
        "author": "John Doe",
        "date": "2026-01-22"
      }
    }
  ],
  "count": 1
}
```

---

## Error Handling

### Standard Error Response Format
```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid input parameters",
  "details": {
    "field": "query",
    "issue": "Query cannot be empty"
  },
  "timestamp": "2026-01-22T10:31:00Z"
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| VALIDATION_ERROR | 400 | Invalid input parameters |
| UNAUTHORIZED | 401 | Authentication required |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

### Rate Limiting
- **Default Limit:** 100 requests per minute per client
- **Headers:** Rate limit info in response headers
- **Retry-After:** Seconds to wait before retry

---

## Data Models

### DocumentMetadata
```json
{
  "document_id": "string (UUID)",
  "filename": "string",
  "file_type": "enum (pdf, txt, docx, html, md)",
  "size_bytes": "integer",
  "created_at": "datetime (ISO 8601)",
  "updated_at": "datetime (ISO 8601)",
  "status": "enum (pending, processing, completed, failed)",
  "metadata": "object"
}
```

### TextChunk
```json
{
  "chunk_id": "string (UUID)",
  "document_id": "string (UUID)",
  "text": "string",
  "chunk_index": "integer",
  "start_char": "integer",
  "end_char": "integer",
  "metadata": "object"
}
```

### EmbeddingVector
```json
{
  "vector_id": "string (UUID)",
  "chunk_id": "string (UUID)",
  "embedding": "array[float]",
  "model_name": "string",
  "dimension": "integer",
  "created_at": "datetime (ISO 8601)"
}
```

### QueryRequest
```json
{
  "query_id": "string (UUID)",
  "query": "string",
  "query_type": "enum (semantic, hybrid, keyword)",
  "top_k": "integer (1-100)",
  "filters": "object",
  "metadata": "object"
}
```

### RetrievalResult
```json
{
  "chunk_id": "string (UUID)",
  "document_id": "string (UUID)",
  "text": "string",
  "score": "float (0-1)",
  "metadata": "object"
}
```

### GenerationRequest
```json
{
  "request_id": "string (UUID)",
  "query": "string",
  "context": "array[RetrievalResult]",
  "model_name": "string",
  "max_tokens": "integer (1-4096)",
  "temperature": "float (0-2)",
  "metadata": "object"
}
```

### GenerationResponse
```json
{
  "request_id": "string (UUID)",
  "response": "string",
  "model_name": "string",
  "tokens_used": "integer",
  "processing_time_ms": "integer",
  "metadata": "object"
}
```

---

## SDK Examples

### Python SDK
```python
from rag_client import RAGClient

# Initialize client
client = RAGClient(
    base_url="http://localhost:8000",
    token="your_jwt_token"
)

# Upload document
document = client.documents.upload(
    file_path="document.pdf"
)

# Query documents
results = client.query.process(
    query="What is machine learning?",
    top_k=5
)

# Generate response
response = client.generation.generate(
    query="Explain embeddings",
    context=results
)
```

### JavaScript SDK
```javascript
import { RAGClient } from '@rag-system/client';

// Initialize client
const client = new RAGClient({
  baseURL: 'http://localhost:8000',
  token: 'your_jwt_token'
});

// Upload document
const document = await client.documents.upload(file);

// Query documents
const results = await client.query.process({
  query: 'What is machine learning?',
  topK: 5
});

// Generate response
const response = await client.generation.generate({
  query: 'Explain embeddings',
  context: results
});
```

---

## API Versioning

### Version Strategy
- **URL Versioning:** `/v1/documents`, `/v2/documents`
- **Header Versioning:** `Accept: application/vnd.rag.v1+json`
- **Deprecation Policy:** 6 months notice
- **Backward Compatibility:** Maintained within major versions

### Current Version
- **Version:** 1.0.0
- **Status:** Stable
- **Deprecation:** Not scheduled

---

## Testing

### API Testing Examples
```bash
# Health check
curl -f http://localhost:8000/health

# Upload document
curl -X POST "http://localhost:8000/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf"

# Query documents
curl -X POST "http://localhost:8000/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}'
```

### Load Testing
```bash
# Using Apache Bench
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/health

# Using wrk
wrk -t12 -c400 -d30s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/query
```

---

## OpenAPI Specification

### Interactive Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

### Download Specification
```bash
# Download OpenAPI spec
curl -o openapi.json http://localhost:8000/openapi.json

# Generate client SDKs
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o python-sdk
```

---

## Support

### Getting Help
- **Documentation:** https://docs.rag-system.com
- **API Reference:** https://api.rag-system.com/docs
- **Support:** support@rag-system.com
- **Community:** https://community.rag-system.com

### Reporting Issues
- **Bug Reports:** GitHub Issues
- **Feature Requests:** GitHub Discussions
- **Security Issues:** security@rag-system.com

### Status Page
- **Service Status:** https://status.rag-system.com
- **Uptime History:** Available on status page
- **Incident Reports:** Posted on status page
