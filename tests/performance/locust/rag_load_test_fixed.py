#!/usr/bin/env python3
"""
Fixed Locust load test for RAG System with correct API endpoints
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

class RAGUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1
    
    def on_start(self):
        """Called when a simulated user starts"""
        # Simulate authentication token
        self.auth_token = f"test-token-{random.randint(1000, 9999)}"
        self.headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        # Warm up with health check
        try:
            response = self.client.get("/health", timeout=5)
            print(f"Health check: {response.status_code}")
        except Exception as e:
            print(f"Health check failed: {e}")
    
    @task(40)
    def query(self):
        """Perform RAG query - 40% of operations"""
        payload = {
            "query": random.choice(QUERIES),
            "top_k": random.randint(3, 7),
            "retrieval_strategy": "hybrid",
            "include_sources": True
        }
        
        with self.client.post(
            "/query",  # Fixed: removed /api/v1 prefix
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure(f"API returned error: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 403:
                response.failure("Authentication failed")
            elif response.status_code == 404:
                response.failure("Endpoint not found")
            else:
                response.failure(f"Status code: {response.status_code}")
    
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
            "/documents/upload",  # Fixed endpoint
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code in [200, 202]:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure(f"Upload failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 403:
                response.failure("Authentication failed")
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task(20)
    def list_documents(self):
        """List documents - 20% of operations (simpler than search)"""
        with self.client.get(
            "/documents",  # Fixed endpoint
            headers=self.headers,
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure(f"List failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 403:
                response.failure("Authentication failed")
            else:
                response.failure(f"List failed: {response.status_code}")
    
    @task(15)
    def health_check(self):
        """Health check - 15% of operations"""
        with self.client.get(
            "/health",
            catch_response=True,
            timeout=2
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure("Service not healthy")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(5)
    def list_models(self):
        """List available models - 5% of operations"""
        with self.client.get(
            "/models",
            headers=self.headers,
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure(f"Models list failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 403:
                response.failure("Authentication failed")
            else:
                response.failure(f"Models list failed: {response.status_code}")


class HeavyUser(RAGUser):
    """Heavy user for stress testing"""
    wait_time = between(0.5, 1.5)
    weight = 0
    
    @task(100)
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
            headers=self.headers,
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'success' in data and data['success']:
                        response.success()
                    else:
                        response.failure(f"Heavy query failed: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in heavy response")
            elif response.status_code == 429:
                response.failure("Rate limited during heavy load")
            elif response.status_code == 503:
                response.failure("Service unavailable under heavy load")
            else:
                response.failure(f"Heavy query failed: {response.status_code}")


# Event handlers for metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Custom request handling for metrics"""
    if exception:
        print(f"Request failed: {name} - {exception}")
    
    # Log slow requests
    if response_time > 5000:
        print(f"Slow request: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Starting RAG System Load Test (Fixed)")
    print(f"Target: {environment.host}")
    print("Using correct API endpoints")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("Load test completed")
    
    # Print summary statistics
    if hasattr(environment.stats, 'total'):
        stats = environment.stats
        print(f"Total requests: {stats.total.num_requests}")
        print(f"Failures: {stats.total.num_failures}")
        print(f"Failure rate: {stats.total.fail_ratio:.2%}")
        print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
