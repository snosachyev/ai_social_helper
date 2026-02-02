// k6 Scaled Load Test Script for 1000+ Users
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
let errorRate = new Rate('errors');

// Test configuration for 1000+ users
export let options = {
  stages: [
    { duration: '30s', target: 100 },   // Warm up
    { duration: '60s', target: 500 },   // Ramp up
    { duration: '120s', target: 1000 }, // Peak load
    { duration: '60s', target: 500 },   // Scale down
    { duration: '30s', target: 0 },      // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],   // 95% under 1s (more realistic for scaled system)
    http_req_failed: ['rate<0.1'],       // Less than 10% errors acceptable for 1000+ users
    errors: ['rate<0.1'],                // Custom error rate
  },
};

const BASE_URL = 'http://localhost:80'; // Using load balancer
const TEST_QUERIES = [
  'What is machine learning?',
  'How does Redis work?',
  'Explain microservices architecture',
  'What are the benefits of PostgreSQL?',
  'How to optimize database performance?',
  'What is load balancing?',
  'Explain horizontal scaling',
  'How does Nginx work?',
  'What are API gateways?',
  'How to handle 1000 concurrent users?'
];

export function setup() {
  console.log('🚀 Starting scaled load test for 1000+ users...');
  console.log(`📊 Target: ${BASE_URL} (Load Balancer)`);
  console.log('⚡ Testing with Nginx + 3 API Gateways');
}

export default function() {
  let token = `test-load-token-${Math.floor(Math.random() * 1000) + 1}`;
  let headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Load-Test': 'true',
    'X-User-ID': `user-${Math.floor(Math.random() * 10000)}`
  };
  
  // Realistic endpoint distribution for high load
  let endpoint = Math.random();
  
  if (endpoint < 0.50) {
    // 50% - Query requests (most common)
    testQueryEndpoint(headers);
    
  } else if (endpoint < 0.70) {
    // 20% - Document upload (resource intensive)
    testUploadEndpoint(headers);
    
  } else if (endpoint < 0.85) {
    // 15% - List documents
    testListEndpoint(headers);
    
  } else if (endpoint < 0.95) {
    // 10% - Models list
    testModelsEndpoint(headers);
    
  } else {
    // 5% - Health check (lightweight)
    testHealthEndpoint();
  }
  
  // Reduced think time for high load testing
  sleep(Math.random() * 1 + 0.2); // 0.2-1.2 seconds
}

function testQueryEndpoint(headers) {
  let query = TEST_QUERIES[Math.floor(Math.random() * TEST_QUERIES.length)];
  
  let queryResponse = http.post(`${BASE_URL}/query`, JSON.stringify({
    query: query,
    top_k: Math.floor(Math.random() * 5) + 3,
    retrieval_strategy: 'hybrid',
    include_sources: true,
    user_context: {
      session_id: `session-${Math.floor(Math.random() * 1000)}`,
      user_preferences: ['fast', 'accurate']
    }
  }), { headers });
  
  let querySuccess = check(queryResponse, {
    'query status is 200': (r) => r.status === 200,
    'query response time < 2000ms': (r) => r.timings.duration < 2000,
    'query has response body': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!querySuccess);
  
  if (!querySuccess && queryResponse.status >= 500) {
    console.log(`❌ Query failed: ${queryResponse.status} - Server Error`);
  } else if (!querySuccess && queryResponse.status === 429) {
    console.log(`⚠️ Query rate limited: 429`);
  }
}

function testUploadEndpoint(headers) {
  let uploadResponse = http.post(`${BASE_URL}/documents/upload`, JSON.stringify({
    filename: `test_doc_${Math.random()}.pdf`,
    content_type: 'application/pdf',
    size: Math.floor(Math.random() * 5000000) + 1000000,
    metadata: {
      author: `user-${Math.floor(Math.random() * 1000)}`,
      category: 'test',
      priority: 'normal'
    }
  }), { headers });
  
  let uploadSuccess = check(uploadResponse, {
    'upload status is 200': (r) => r.status === 200,
    'upload response time < 5000ms': (r) => r.timings.duration < 5000,
    'upload has response': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!uploadSuccess);
  
  if (!uploadSuccess && uploadResponse.status === 429) {
    console.log(`⚠️ Upload rate limited: 429`);
  }
}

function testListEndpoint(headers) {
  let listResponse = http.get(`${BASE_URL}/documents?limit=20&offset=${Math.floor(Math.random() * 100)}`, { headers });
  
  let listSuccess = check(listResponse, {
    'list status is 200': (r) => r.status === 200,
    'list response time < 1000ms': (r) => r.timings.duration < 1000,
    'list has array response': (r) => {
      try {
        return JSON.parse(r.body).documents.constructor === Array;
      } catch (e) {
        return false;
      }
    }
  });
  
  errorRate.add(!listSuccess);
}

function testModelsEndpoint(headers) {
  let modelsResponse = http.get(`${BASE_URL}/models`, { headers });
  
  let modelsSuccess = check(modelsResponse, {
    'models status is 200': (r) => r.status === 200,
    'models response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!modelsSuccess);
}

function testHealthEndpoint() {
  let healthResponse = http.get(`${BASE_URL}/health`);
  
  let healthSuccess = check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!healthSuccess);
}

export function teardown() {
  console.log('✅ Scaled load test completed');
  console.log('📈 Check results for 1000+ users performance analysis');
  console.log('🔧 If errors > 10%, consider scaling up or optimizing');
}
