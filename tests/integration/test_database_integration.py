#!/usr/bin/env python3
"""Simple integration test for database connectivity"""

import sys
import os
import psycopg2
import redis
from datetime import datetime

def test_postgres_connection():
    """Test PostgreSQL connection"""
    print("🧪 Testing PostgreSQL connection...")
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='test',
            password='test',
            database='test_rag'
        )
        
        # Test basic query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        # Create test table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Insert test data
        cursor.execute(
            "INSERT INTO test_table (message) VALUES (%s) RETURNING id;",
            ("Integration test message",)
        )
        test_id = cursor.fetchone()[0]
        
        # Query test data
        cursor.execute("SELECT * FROM test_table WHERE id = %s;", (test_id,))
        result = cursor.fetchone()
        
        # Cleanup
        cursor.execute("DROP TABLE IF EXISTS test_table;")
        conn.commit()
        conn.close()
        
        print(f"✅ PostgreSQL connection works! Version: {version[0][:50]}...")
        print(f"✅ Data insertion/retrieval works! Test ID: {test_id}")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connection"""
    print("🧪 Testing Redis connection...")
    
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Test basic operations
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        
        # Test list operations
        r.lpush('test_list', 'item1', 'item2', 'item3')
        list_length = r.llen('test_list')
        list_items = r.lrange('test_list', 0, -1)
        
        # Cleanup
        r.delete('test_key', 'test_list')
        
        print(f"✅ Redis connection works! Value: {value}")
        print(f"✅ List operations work! Length: {list_length}, Items: {list_items}")
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_database_integration():
    """Test integration between databases"""
    print("🧪 Testing database integration...")
    
    try:
        # Connect to both databases
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='test',
            password='test',
            database='test_rag'
        )
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Simulate document processing workflow
        cursor = conn.cursor()
        
        # Create document metadata in PostgreSQL
        cursor.execute("""
            CREATE TEMPORARY TABLE test_documents (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute(
            "INSERT INTO test_documents (filename, status) VALUES (%s, %s) RETURNING id;",
            ("test_document.pdf", "processing")
        )
        doc_id = cursor.fetchone()[0]
        
        # Store processing status in Redis
        r.set(f"doc:{doc_id}:status", "processing")
        r.set(f"doc:{doc_id}:progress", "25")
        
        # Update status in PostgreSQL
        cursor.execute(
            "UPDATE test_documents SET status = %s WHERE id = %s;",
            ("completed", doc_id)
        )
        
        # Update Redis
        r.set(f"doc:{doc_id}:status", "completed")
        r.set(f"doc:{doc_id}:progress", "100")
        
        # Verify integration
        cursor.execute("SELECT status FROM test_documents WHERE id = %s;", (doc_id,))
        pg_status = cursor.fetchone()[0]
        redis_status = r.get(f"doc:{doc_id}:status")
        redis_progress = r.get(f"doc:{doc_id}:progress")
        
        conn.commit()
        conn.close()
        
        # Cleanup Redis
        r.delete(f"doc:{doc_id}:status", f"doc:{doc_id}:progress")
        
        print(f"✅ Database integration works!")
        print(f"✅ Document ID: {doc_id}")
        print(f"✅ PostgreSQL status: {pg_status}")
        print(f"✅ Redis status: {redis_status}, progress: {redis_progress}")
        
        return pg_status == "completed" and redis_status == "completed"
        
    except Exception as e:
        print(f"❌ Database integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_integration_tests():
    """Run all integration tests"""
    print("🚀 Starting integration tests...\n")
    
    results = []
    
    # Test individual connections
    results.append(test_postgres_connection())
    print()
    
    results.append(test_redis_connection())
    print()
    
    # Test integration
    results.append(test_database_integration())
    print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        return True
    else:
        print("❌ Some integration tests failed!")
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
