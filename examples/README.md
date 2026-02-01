# 📚 RAG System Examples

This directory contains practical examples demonstrating how to use the RAG System's capabilities.

## 🗂️ Available Examples

### 🤖 Model Service Integration
- **[model_service_example.py](model_service_example.py)** - Complete example of using the model service for text generation and embeddings

### 📄 Document Processing
```python
# Upload and process documents
import requests

# Upload a PDF document
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/documents/upload',
        files={'file': f}
    )
```

### 🔍 Semantic Search
```python
# Perform semantic search
query_data = {
    "query": "What is machine learning?",
    "top_k": 5,
    "filters": {"document_type": "academic"}
}

response = requests.post(
    'http://localhost:8000/query',
    json=query_data
)
```

### 🎯 RAG Generation
```python
# Generate context-aware responses
generation_data = {
    "query": "Explain neural networks",
    "context": ["relevant document chunks..."],
    "max_tokens": 500,
    "temperature": 0.7
}

response = requests.post(
    'http://localhost:8000/generate',
    json=generation_data
)
```

## 🚀 Quick Start Examples

### 1. Basic Document Upload
```bash
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@example.pdf"
```

### 2. Simple Query
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?", "top_k": 3}'
```

### 3. Generate Response
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain deep learning", "context": [...]}'
```

## 🛠️ Advanced Examples

### Batch Document Processing
```python
import os
import requests

def upload_documents(folder_path):
    """Upload all documents from a folder"""
    uploaded = []
    
    for filename in os.listdir(folder_path):
        if filename.endswith(('.pdf', '.txt', '.docx')):
            with open(os.path.join(folder_path, filename), 'rb') as f:
                response = requests.post(
                    'http://localhost:8000/documents/upload',
                    files={'file': f}
                )
                if response.status_code == 200:
                    uploaded.append(filename)
    
    return uploaded
```

### Hybrid Search
```python
def hybrid_search(query, semantic_weight=0.7):
    """Combine semantic and keyword search"""
    data = {
        "query": query,
        "search_type": "hybrid",
        "semantic_weight": semantic_weight,
        "top_k": 10
    }
    
    response = requests.post(
        'http://localhost:8000/query',
        json=data
    )
    
    return response.json()
```

### Streaming Generation
```python
import requests
import json

def stream_response(query, context):
    """Stream generation response"""
    data = {
        "query": query,
        "context": context,
        "stream": True
    }
    
    with requests.post(
        'http://localhost:8000/generate',
        json=data,
        stream=True
    ) as response:
        for line in response.iter_lines():
            if line:
                yield json.loads(line.decode('utf-8'))
```

## 📊 Performance Testing

### Load Testing Example
```python
import asyncio
import aiohttp
import time

async def benchmark_query(query, num_requests=100):
    """Benchmark query performance"""
    url = "http://localhost:8000/query"
    data = {"query": query, "top_k": 5}
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(num_requests):
            task = session.post(url, json=data)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    successful = sum(1 for r in responses if r.status == 200)
    
    print(f"Completed {num_requests} requests in {total_time:.2f}s")
    print(f"Success rate: {successful/num_requests*100:.1f}%")
    print(f"Average response time: {total_time/num_requests:.3f}s")
```

## 🔧 Configuration Examples

### Custom Embedding Model
```python
# Configure custom embedding model
config = {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "batch_size": 32,
    "cache_size": 1000
}

response = requests.put(
    'http://localhost:8000/config/embedding',
    json=config
)
```

### Vector Database Settings
```python
# Configure vector database
vector_config = {
    "vector_db": "chromadb",
    "collection_name": "documents",
    "embedding_function": "default",
    "persist_directory": "./chroma_db"
}

response = requests.put(
    'http://localhost:8000/config/vector_db',
    json=vector_config
)
```

## 🧪 Testing Examples

### Integration Test
```python
def test_rag_pipeline():
    """Test complete RAG pipeline"""
    
    # 1. Upload document
    with open('test_document.txt', 'w') as f:
        f.write("Machine learning is a subset of artificial intelligence...")
    
    with open('test_document.txt', 'rb') as f:
        upload_response = requests.post(
            'http://localhost:8000/documents/upload',
            files={'file': f}
        )
    
    assert upload_response.status_code == 200
    
    # 2. Query documents
    query_response = requests.post(
        'http://localhost:8000/query',
        json={"query": "What is machine learning?", "top_k": 3}
    )
    
    assert query_response.status_code == 200
    results = query_response.json()
    assert len(results['results']) > 0
    
    # 3. Generate response
    context = [r['text'] for r in results['results']]
    gen_response = requests.post(
        'http://localhost:8000/generate',
        json={
            "query": "Explain machine learning",
            "context": context
        }
    )
    
    assert gen_response.status_code == 200
    response_text = gen_response.json()['response']
    assert len(response_text) > 0
    
    print("✅ RAG pipeline test passed!")
```

## 📝 Best Practices

### 1. Error Handling
```python
import requests
from requests.exceptions import RequestException

def safe_api_call(url, data=None, max_retries=3):
    """Safe API call with retries"""
    for attempt in range(max_retries):
        try:
            if data:
                response = requests.post(url, json=data, timeout=30)
            else:
                response = requests.get(url, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 2. Rate Limiting
```python
import time
from typing import List

def rate_limited_requests(urls: List[str], delay=1.0):
    """Make requests with rate limiting"""
    results = []
    
    for url in urls:
        response = requests.get(url)
        results.append(response.json())
        time.sleep(delay)  # Rate limiting
    
    return results
```

### 3. Context Management
```python
def optimize_context(context: List[str], max_tokens=2000):
    """Optimize context for generation"""
    # Simple truncation based on token count
    total_tokens = sum(len(text.split()) for text in context)
    
    if total_tokens <= max_tokens:
        return context
    
    # Keep most relevant chunks
    optimized = []
    current_tokens = 0
    
    for chunk in context:
        chunk_tokens = len(chunk.split())
        if current_tokens + chunk_tokens <= max_tokens:
            optimized.append(chunk)
            current_tokens += chunk_tokens
        else:
            break
    
    return optimized
```

---

## 🚀 Getting Started

1. **Start the services**: `python scripts/deployment/start_services.py`
2. **Run examples**: `python examples/model_service_example.py`
3. **Check health**: `python scripts/health/health_check.py`
4. **View API docs**: http://localhost:8000/docs

For more examples, check the [API Reference](../docs/api/API_REFERENCE.md) and [Development Guide](../docs/development/).
