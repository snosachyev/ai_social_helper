#!/usr/bin/env python3
"""
Simple HTTP Load Test with threading for high concurrency
"""

import requests
import threading
import time
import random
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import sys

# Configuration
BASE_URL = "http://localhost:8000"
TEST_DURATION = 120  # seconds
MAX_WORKERS = 1000

# Test data
QUERIES = [
    "What is machine learning?",
    "How do neural networks work?",
    "Explain deep learning concepts",
    "What are transformers in AI?",
    "How to optimize model performance?"
]

def get_test_token():
    """Get a random test token"""
    token_id = random.randint(1, 100)
    return f"test-load-token-{token_id:03d}"

def get_auth_headers():
    """Get authentication headers"""
    token = get_test_token()
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Load-Test': 'true'
    }

class LoadTestWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.results = []
        
    def run_health_check(self):
        """Run health check"""
        try:
            start_time = time.time()
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            end_time = time.time()
            
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/health',
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'success': response.status_code == 200
            })
        except Exception as e:
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/health',
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'error': str(e)
            })
    
    def run_query(self):
        """Run RAG query"""
        try:
            payload = {
                "query": random.choice(QUERIES),
                "top_k": random.randint(3, 7),
                "retrieval_strategy": "hybrid",
                "include_sources": True
            }
            
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/query",
                json=payload,
                headers=get_auth_headers(),
                timeout=10
            )
            end_time = time.time()
            
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/query',
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'success': response.status_code == 200
            })
        except Exception as e:
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/query',
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'error': str(e)
            })
    
    def run_upload_document(self):
        """Upload document"""
        try:
            payload = {
                "filename": f"test_doc_{self.worker_id}.pdf",
                "content_type": "application/pdf",
                "size": random.randint(1000000, 10000000),
                "metadata": {
                    "category": "technical",
                    "language": "en",
                    "tags": ["ai", "ml", "research"]
                }
            }
            
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/documents/upload",
                json=payload,
                headers=get_auth_headers(),
                timeout=30
            )
            end_time = time.time()
            
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/documents/upload',
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'success': response.status_code == 200
            })
        except Exception as e:
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/documents/upload',
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'error': str(e)
            })
    
    def run_list_documents(self):
        """List documents"""
        try:
            start_time = time.time()
            response = requests.get(
                f"{BASE_URL}/documents",
                headers=get_auth_headers(),
                timeout=5
            )
            end_time = time.time()
            
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/documents',
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'success': response.status_code == 200
            })
        except Exception as e:
            self.results.append({
                'worker_id': self.worker_id,
                'endpoint': '/documents',
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'error': str(e)
            })
    
    def worker_loop(self, duration: int):
        """Main worker loop"""
        end_time = time.time() + duration
        
        while time.time() < end_time:
            # Random operation selection
            operation = random.choices(
                ['health', 'query', 'upload', 'list'],
                weights=[10, 35, 25, 30],
                k=1
            )[0]
            
            if operation == 'health':
                self.run_health_check()
            elif operation == 'query':
                self.run_query()
            elif operation == 'upload':
                self.run_upload_document()
            elif operation == 'list':
                self.run_list_documents()
            
            # Small delay between requests
            time.sleep(random.uniform(0.1, 0.5))

def run_load_test(num_workers: int, duration: int):
    """Run load test with specified number of workers"""
    print(f"🚀 Starting load test with {num_workers} workers for {duration} seconds")
    print("=" * 60)
    
    # Create workers
    workers = [LoadTestWorker(i) for i in range(num_workers)]
    
    # Start timing
    start_time = time.time()
    
    # Run workers with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all worker tasks
        futures = [
            executor.submit(worker.worker_loop, duration)
            for worker in workers
        ]
        
        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Worker error: {e}")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Collect all results
    all_results = []
    for worker in workers:
        all_results.extend(worker.results)
    
    # Analyze results
    analyze_results(all_results, total_time, num_workers)

def analyze_results(results: List[Dict], total_time: float, num_workers: int):
    """Analyze test results"""
    print(f"\n📊 Load Test Results for {num_workers} workers")
    print("=" * 50)
    
    total_requests = len(results)
    successful_requests = sum(1 for r in results if r['success'])
    failed_requests = total_requests - successful_requests
    
    success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
    requests_per_second = total_requests / total_time if total_time > 0 else 0
    
    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {successful_requests}")
    print(f"Failed requests: {failed_requests}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Requests per second: {requests_per_second:.1f}")
    print(f"Test duration: {total_time:.1f} seconds")
    
    # Response time analysis
    successful_response_times = [r['response_time'] for r in results if r['success']]
    
    if successful_response_times:
        avg_response_time = statistics.mean(successful_response_times)
        median_response_time = statistics.median(successful_response_times)
        p95_response_time = statistics.quantiles(successful_response_times, n=20)[18]  # 95th percentile
        max_response_time = max(successful_response_times)
        
        print(f"\n⏱️ Response Times:")
        print(f"Average: {avg_response_time:.1f}ms")
        print(f"Median: {median_response_time:.1f}ms")
        print(f"95th percentile: {p95_response_time:.1f}ms")
        print(f"Maximum: {max_response_time:.1f}ms")
    
    # Endpoint breakdown
    print(f"\n📋 Endpoint Breakdown:")
    endpoints = {}
    for result in results:
        endpoint = result['endpoint']
        if endpoint not in endpoints:
            endpoints[endpoint] = {'total': 0, 'success': 0}
        endpoints[endpoint]['total'] += 1
        if result['success']:
            endpoints[endpoint]['success'] += 1
    
    for endpoint, stats in endpoints.items():
        endpoint_success_rate = (stats['success'] / stats['total'] * 100)
        print(f"{endpoint}: {stats['success']}/{stats['total']} ({endpoint_success_rate:.1f}%)")
    
    # Error analysis
    errors = [r for r in results if not r['success']]
    if errors:
        print(f"\n❌ Error Analysis:")
        error_types = {}
        for error in errors:
            error_key = f"Status {error['status_code']}" if error['status_code'] > 0 else "Connection Error"
            if error_key not in error_types:
                error_types[error_key] = 0
            error_types[error_key] += 1
        
        for error_type, count in error_types.items():
            print(f"{error_type}: {count}")
    
    # Performance assessment
    print(f"\n🎯 Performance Assessment:")
    if success_rate >= 95:
        print("✅ Excellent performance - Ready for production!")
    elif success_rate >= 90:
        print("⚠️ Good performance with minor issues")
    elif success_rate >= 75:
        print("⚠️ Acceptable performance but needs optimization")
    else:
        print("❌ Poor performance - significant issues found")
    
    return {
        'total_requests': total_requests,
        'success_rate': success_rate,
        'requests_per_second': requests_per_second,
        'avg_response_time': statistics.mean(successful_response_times) if successful_response_times else 0
    }

def main():
    """Main function"""
    print("🚀 Simple HTTP Load Test for RAG System")
    print("=" * 50)
    
    # Test with different worker counts
    test_scenarios = [
        (100, 60),
        (200, 60),
        (500, 90),
        (1000, 120)
    ]
    
    results_summary = []
    
    for num_workers, duration in test_scenarios:
        try:
            result = run_load_test(num_workers, duration)
            results_summary.append({
                'workers': num_workers,
                **result
            })
            
            print(f"\n⏳ Waiting 10 seconds before next test...")
            time.sleep(10)
            
        except KeyboardInterrupt:
            print(f"\n⚠️ Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            continue
    
    # Final summary
    print(f"\n🏁 Final Summary")
    print("=" * 50)
    for summary in results_summary:
        print(f"{summary['workers']} workers: {summary['success_rate']:.1f}% success, {summary['requests_per_second']:.1f} RPS")

if __name__ == "__main__":
    main()
