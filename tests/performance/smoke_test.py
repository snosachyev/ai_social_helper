#!/usr/bin/env python3
"""
Quick smoke test to verify system readiness for load testing
"""

import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_health_endpoints():
    """Test basic health endpoints"""
    print("🔍 Testing health endpoints...")
    
    # Test API Gateway health
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"API Gateway: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"❌ API Gateway failed: {e}")
        return False
    
    # Test individual services
    services = [
        ("Auth Service", 8007),
        ("Embedding Service", 8002),
    ]
    
    for name, port in services:
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=5)
            print(f"{name}: {response.status_code}")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
    
    return True

def test_basic_query():
    """Test basic query functionality"""
    print("\n🧪 Testing basic query...")
    
    # Try without auth first
    try:
        response = requests.post(f"{BASE_URL}/api/v1/query", 
                               json={"query": "test", "top_k": 3}, 
                               timeout=10)
        print(f"Query without auth: {response.status_code}")
        if response.status_code == 403:
            print("✅ Auth required - expected")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False
    
    return True

def test_system_load():
    """Check current system load"""
    print("\n📊 Current system load:")
    
    import psutil
    print(f"CPU Usage: {psutil.cpu_percent()}%")
    print(f"Memory Usage: {psutil.virtual_memory().percent}%")
    print(f"Available Memory: {psutil.virtual_memory().available / 1024**3:.1f}GB")

def main():
    print("🚀 RAG System Smoke Test")
    print("=" * 50)
    
    # Test system load
    test_system_load()
    
    # Test endpoints
    if not test_health_endpoints():
        print("\n❌ System not ready for load testing")
        sys.exit(1)
    
    if not test_basic_query():
        print("\n❌ Basic functionality not working")
        sys.exit(1)
    
    print("\n✅ System ready for load testing!")
    print("\nNext steps:")
    print("1. Run: source /tmp/locust-env/bin/activate")
    print("2. Run: locust -f tests/performance/locust/rag_load_test.py --host http://localhost:8000")
    print("3. Open: http://localhost:8089")

if __name__ == "__main__":
    main()
