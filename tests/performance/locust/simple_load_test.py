#!/usr/bin/env python3
"""
Simple load test for RAG System without authentication
Focus on basic performance and availability
"""

import random
import json
import time
from locust import HttpUser, task, between, events

class SimpleRAGUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1
    
    def on_start(self):
        """Called when a simulated user starts"""
        print("Starting simple load test user")
        
        # Test basic connectivity
        try:
            response = self.client.get("/health", timeout=5)
            print(f"Initial health check: {response.status_code}")
        except Exception as e:
            print(f"Health check failed: {e}")
    
    @task(30)
    def health_check(self):
        """Health check - 30% of operations"""
        with self.client.get(
            "/health",
            catch_response=True,
            timeout=3
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 403:
                # Expected - auth required
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(25)
    def test_upload_endpoint(self):
        """Test upload endpoint - 25% of operations"""
        payload = {
            "filename": f"test_doc_{random.randint(1000, 9999)}.pdf",
            "content_type": "application/pdf",
            "size": random.randint(1000000, 5000000),
            "metadata": {
                "category": "test",
                "language": "en"
            }
        }
        
        with self.client.post(
            "/test-upload",  # Use test endpoint that doesn't require auth
            json=payload,
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code in [200, 201, 202]:
                response.success()
            else:
                response.failure(f"Test upload failed: {response.status_code}")
    
    @task(20)
    def metrics_endpoint(self):
        """Metrics endpoint - 20% of operations"""
        with self.client.get(
            "/metrics",
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics failed: {response.status_code}")
    
    @task(15)
    def root_endpoint(self):
        """Root endpoint - 15% of operations"""
        with self.client.get(
            "/",
            catch_response=True,
            timeout=3
        ) as response:
            if response.status_code in [200, 403]:  # 403 expected for auth
                response.success()
            else:
                response.failure(f"Root endpoint failed: {response.status_code}")
    
    @task(10)
    def individual_service_health(self):
        """Test individual services directly - 10% of operations"""
        services = [
            ("Auth Service", 8007),
            ("Embedding Service", 8002),
        ]
        
        service_name, port = random.choice(services)
        
        try:
            with self.client.get(
                f"http://localhost:{port}/health",
                catch_response=True,
                timeout=5
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"{service_name} health failed: {response.status_code}")
        except Exception as e:
            # Can't connect to service directly
            response.failure(f"{service_name} connection failed")


class StressUser(SimpleRAGUser):
    """Stress user with higher frequency"""
    wait_time = between(0.2, 1.0)
    weight = 0
    
    @task(50)
    def rapid_health_checks(self):
        """Rapid health checks for stress testing"""
        with self.client.get(
            "/health",
            catch_response=True,
            timeout=2
        ) as response:
            if response.status_code in [200, 403]:
                response.success()
            else:
                response.failure(f"Rapid health check failed: {response.status_code}")
    
    @task(30)
    def rapid_uploads(self):
        """Rapid test uploads"""
        payload = {
            "filename": f"stress_{random.randint(1000, 9999)}.pdf",
            "size": random.randint(100000, 1000000)
        }
        
        with self.client.post(
            "/test-upload",
            json=payload,
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code in [200, 201, 202]:
                response.success()
            else:
                response.failure(f"Rapid upload failed: {response.status_code}")
    
    @task(20)
    def rapid_metrics(self):
        """Rapid metrics checks"""
        with self.client.get(
            "/metrics",
            catch_response=True,
            timeout=3
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Rapid metrics failed: {response.status_code}")


# Event handlers
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("🚀 Starting Simple RAG Load Test")
    print(f"Target: {environment.host}")
    print("Testing without authentication - focus on basic performance")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("\n📊 Load test completed")
    
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
            print("✅ Excellent performance")
        elif success_rate >= 90:
            print("⚠️ Good performance with some issues")
        else:
            print("❌ Performance needs improvement")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests"""
    if response_time > 3000:  # Log requests > 3 seconds
        print(f"🐌 Slow request: {name} took {response_time}ms")
