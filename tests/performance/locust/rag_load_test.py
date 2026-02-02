#!/usr/bin/env python3
"""
Locust load test for RAG System
Alternative to k6 tests with Python syntax
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
        # Simulate authentication
        self.auth_token = f"bearer-{random.randint(1000, 9999)}"
        self.headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        # Warm up
        try:
            self.client.get("/health", headers=self.headers)
        except:
            pass
    
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
            "/api/v1/query",
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'results' in data and len(data['results']) > 0:
                        response.success()
                    else:
                        response.failure("No results in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
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
            "/api/v1/documents/upload",
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code in [200, 202]:
                try:
                    data = response.json()
                    if 'document_id' in data:
                        response.success()
                    else:
                        response.failure("No document_id in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task(20)
    def search_documents(self):
        """Search documents - 20% of operations"""
        query = random.choice(QUERIES)
        payload = {
            "query": query,
            "limit": random.randint(5, 15),
            "filters": {
                "category": "technical",
                "language": "en"
            }
        }
        
        with self.client.post(
            "/api/v1/documents/search",
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'documents' in data and len(data['documents']) > 0:
                        response.success()
                    else:
                        response.failure("No documents found")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(15)
    def health_check(self):
        """Health check - 15% of operations"""
        with self.client.get(
            "/health",
            headers=self.headers,
            catch_response=True,
            timeout=2
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('status') == 'healthy':
                        response.success()
                    else:
                        response.failure("Service not healthy")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Health check failed: {response.status_code}")


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
            "/api/v1/query",
            json=payload,
            headers=self.headers,
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if all(key in data for key in ['results', 'sources', 'explanations']):
                        response.success()
                    else:
                        response.failure("Incomplete heavy response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in heavy response")
            elif response.status_code == 429:
                response.failure("Rate limited during heavy load")
            elif response.status_code == 503:
                response.failure("Service unavailable under heavy load")
            else:
                response.failure(f"Heavy query failed: {response.status_code}")


class FailureTestUser(HttpUser):
    """User for testing failure scenarios"""
    wait_time = between(1, 2)
    weight = 0
    
    def on_start(self):
        self.auth_token = f"failure-test-{random.randint(1000, 9999)}"
        self.headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json',
            'X-Failure-Test': 'true'
        }
    
    @task
    def test_resilience(self):
        """Test system resilience under failures"""
        # Simulate different failure scenarios
        scenarios = [
            self.test_embedding_failure,
            self.test_generation_failure,
            self.test_database_failure,
            self.test_circuit_breaker
        ]
        
        random.choice(scenarios)()
    
    def test_embedding_failure(self):
        """Test embedding service failure"""
        payload = {
            "query": "Test query for embedding failure",
            "retrieval_strategy": "vector_only"
        }
        
        with self.client.post(
            "/api/v1/query",
            json=payload,
            headers={**self.headers, 'X-Failure-Scenario': 'embedding-service'},
            catch_response=True,
            timeout=15
        ) as response:
            # Should handle gracefully or use fallback
            if response.status_code in [200, 202, 503]:
                response.success()
            else:
                response.failure(f"Embedding failure not handled: {response.status_code}")
    
    def test_generation_failure(self):
        """Test generation service failure"""
        payload = {
            "query": "Test query for generation failure",
            "generate_response": True,
            "max_tokens": 100
        }
        
        with self.client.post(
            "/api/v1/generate",
            json=payload,
            headers={**self.headers, 'X-Failure-Scenario': 'generation-service'},
            catch_response=True,
            timeout=20
        ) as response:
            if response.status_code in [200, 202, 503]:
                response.success()
            else:
                response.failure(f"Generation failure not handled: {response.status_code}")
    
    def test_database_failure(self):
        """Test database failure"""
        with self.client.get(
            "/api/v1/documents",
            headers={**self.headers, 'X-Failure-Scenario': 'database'},
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code in [200, 503, 504]:
                response.success()
            else:
                response.failure(f"Database failure not handled: {response.status_code}")
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        # Rapid requests to trigger circuit breaker
        for _ in range(5):
            with self.client.get(
                "/api/v1/status",
                headers=self.headers,
                catch_response=True,
                timeout=2
            ) as response:
                if response.status_code == 503:
                    # Circuit breaker activated
                    response.success()
                    break
                elif response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Circuit breaker test failed: {response.status_code}")


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
    print("Starting RAG System Load Test")
    print(f"Target: {environment.host}")


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
