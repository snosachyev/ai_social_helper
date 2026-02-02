#!/usr/bin/env python3
"""
Load test with working authentication for RAG System
"""

import random
import json
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask

# Test data
QUERIES = [
    "What is machine learning?",
    "How do neural networks work?",
    "Explain deep learning concepts",
    "What are transformers in AI?",
    "How to optimize model performance?",
    "What is reinforcement learning?",
    "Explain computer vision",
    "How do GPT models work?",
    "What is natural language processing?",
    "How to train AI models?"
]

HEAVY_QUERIES = [
    "Explain the complete architecture of transformer models including attention mechanisms",
    "Compare and contrast different optimization algorithms used in deep learning",
    "Provide a comprehensive analysis of bias and fairness issues in large language models",
    "Describe the complete pipeline for building production-ready ML systems",
    "Explain quantum computing applications in machine learning"
]

DOCUMENTS = [
    'ml_basics.pdf',
    'deep_learning.pdf', 
    'neural_networks.pdf',
    'ai_ethics.pdf',
    'data_science.pdf'
]

def get_test_token():
    """Get a random test token"""
    token_id = random.randint(1, 100)
    return f"test-load-token-{token_id:03d}"

def get_auth_headers():
    """Get authentication headers for load testing"""
    token = get_test_token()
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Load-Test': 'true'  # Bypass rate limiting
    }

class AuthenticatedRAGUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1
    
    def on_start(self):
        """Called when a simulated user starts"""
        print("🚀 Starting authenticated load test user")
        
        # Test authentication
        try:
            headers = get_auth_headers()
            response = self.client.get("/health", headers=headers, timeout=5)
            print(f"Auth test: {response.status_code}")
        except Exception as e:
            print(f"Auth test failed: {e}")
    
    @task(35)
    def query(self):
        """Perform RAG query - 35% of operations"""
        payload = {
            "query": random.choice(QUERIES),
            "top_k": random.randint(3, 7),
            "retrieval_strategy": "hybrid",
            "include_sources": True
        }
        
        with self.client.post(
            "/query",
            json=payload,
            headers=get_auth_headers(),
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'results' in data:
                        response.success()
                    else:
                        response.failure(f"Query failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Query failed with status: {response.status_code}")
    
    @task(25)
    def upload_document(self):
        """Upload document - 25% of operations"""
        payload = {
            "filename": random.choice(DOCUMENTS),
            "content_type": "application/pdf",
            "size": random.randint(1000000, 10000000),
            "metadata": {
                "category": "technical",
                "language": "en",
                "tags": ["ai", "ml", "research"]
            }
        }
        
        with self.client.post(
            "/documents/upload",
            json=payload,
            headers=get_auth_headers(),
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'document_id' in data:
                        response.success()
                    else:
                        response.failure(f"Upload failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Upload failed with status: {response.status_code}")
    
    @task(20)
    def list_documents(self):
        """List documents - 20% of operations"""
        with self.client.get(
            "/documents",
            headers=get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'documents' in data:
                        response.success()
                    else:
                        response.failure(f"List failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"List failed with status: {response.status_code}")
    
    @task(10)
    def list_models(self):
        """List available models - 10% of operations"""
        with self.client.get(
            "/models",
            headers=get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'models' in data:
                        response.success()
                    else:
                        response.failure(f"Models list failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Models list failed with status: {response.status_code}")
    
    @task(10)
    def health_check(self):
        """Health check - 10% of operations"""
        with self.client.get(
            "/health",
            catch_response=True,
            timeout=2
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success'):
                        response.success()
                    else:
                        response.failure("Service not healthy")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Health check failed: {response.status_code}")


class HeavyAuthenticatedUser(AuthenticatedRAGUser):
    """Heavy user for stress testing with authentication"""
    wait_time = between(0.5, 1.5)
    weight = 0
    
    @task(60)
    def heavy_query(self):
        """Heavy RAG queries for stress testing"""
        payload = {
            "query": random.choice(HEAVY_QUERIES),
            "top_k": 10,
            "retrieval_strategy": "comprehensive",
            "include_sources": True,
            "include_explanations": True,
            "max_context_length": 4000,
            "temperature": 0.1
        }
        
        with self.client.post(
            "/query",
            json=payload,
            headers=get_auth_headers(),
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'results' in data:
                        response.success()
                    else:
                        response.failure(f"Heavy query failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in heavy response")
            else:
                response.failure(f"Heavy query failed with status: {response.status_code}")
    
    @task(25)
    def generate_response(self):
        """Generate response - 25% of operations"""
        payload = {
            "query": random.choice(QUERIES),
            "max_tokens": random.randint(100, 500),
            "temperature": random.uniform(0.1, 0.9)
        }
        
        with self.client.post(
            "/generate",
            json=payload,
            headers=get_auth_headers(),
            catch_response=True,
            timeout=20
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and 'response' in data:
                        response.success()
                    else:
                        response.failure(f"Generate failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in generate response")
            else:
                response.failure(f"Generate failed with status: {response.status_code}")
    
    @task(15)
    def load_model(self):
        """Load model - 15% of operations"""
        models = ["gpt-3.5-turbo", "bert-base"]
        model_name = random.choice(models)
        
        with self.client.post(
            f"/models/{model_name}/load",
            headers=get_auth_headers(),
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and data.get('status') == 'loaded':
                        response.success()
                    else:
                        response.failure(f"Model load failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in model load response")
            else:
                response.failure(f"Model load failed with status: {response.status_code}")


# Event handlers
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("🚀 Starting Authenticated RAG Load Test")
    print(f"Target: {environment.host}")
    print("✅ Authentication configured")
    print("📝 Using test tokens: test-load-token-XXX")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("\n📊 Authenticated Load Test Completed")
    
    if hasattr(environment.stats, 'total'):
        stats = environment.stats
        success_rate = (1 - stats.total.fail_ratio) * 100
        
        print(f"Total requests: {stats.total.num_requests}")
        print(f"Successful requests: {stats.total.num_requests - stats.total.num_failures}")
        print(f"Failed requests: {stats.total.num_failures}")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
        print(f"Max response time: {stats.total.max_response_time:.2f}ms")
        
        # Performance assessment
        if success_rate >= 95:
            print("✅ Excellent performance - Ready for production!")
        elif success_rate >= 90:
            print("⚠️ Good performance with minor issues")
        else:
            print("❌ Performance needs improvement")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests"""
    if response_time > 5000:  # Log requests > 5 seconds
        print(f"🐌 Slow request: {name} took {response_time}ms")
