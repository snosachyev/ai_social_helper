// k6 Simple Load Test Script
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
let errorRate = new Rate('errors');

// Test configuration
export let options = {
  stages: [
    { duration: '10s', target: 10 },   // Warm up
    { duration: '20s', target: 50 },   // Ramp up
    { duration: '30s', target: 100 },  // Load test
    { duration: '20s', target: 50 },  // Scale down
    { duration: '10s', target: 0 },    // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% under 500ms
    http_req_failed: ['rate<0.05'],      // Less than 5% errors
    errors: ['rate<0.05'],               // Custom error rate
  },
};

const BASE_URL = 'http://localhost:8000';
const TEST_QUERIES = [
  'What is machine learning?',
  'How does Redis work?',
  'Explain microservices architecture',
  'What are the benefits of PostgreSQL?',
  'How to optimize database performance?'
];

export function setup() {
  console.log('🚀 Starting simple load test...');
  console.log(`📊 Target: ${BASE_URL}`);
}

export default function() {
  let token = `test-load-token-${Math.floor(Math.random() * 100) + 1}`;
  let headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Load-Test': 'true'
  };
  
  // Realistic endpoint distribution
  let endpoint = Math.random();
  
  if (endpoint < 0.40) {
    // 40% - Query requests
    testQueryEndpoint(headers);
    
  } else if (endpoint < 0.60) {
    // 20% - Document upload
    testUploadEndpoint(headers);
    
  } else if (endpoint < 0.80) {
    // 20% - List documents
    testListEndpoint(headers);
    
  } else if (endpoint < 0.90) {
    // 10% - Models list
    testModelsEndpoint(headers);
    
  } else {
    // 10% - Health check
    testHealthEndpoint();
  }
  
  // Realistic think time between requests
  sleep(Math.random() * 2 + 0.5); // 0.5-2.5 seconds
}

function testQueryEndpoint(headers) {
  let query = TEST_QUERIES[Math.floor(Math.random() * TEST_QUERIES.length)];
  
  let queryResponse = http.post(`${BASE_URL}/query`, JSON.stringify({
    query: query,
    top_k: Math.floor(Math.random() * 5) + 3,
    retrieval_strategy: 'hybrid',
    include_sources: true
  }), { headers });
  
  let querySuccess = check(queryResponse, {
    'query status is 200': (r) => r.status === 200,
    'query response time < 1000ms': (r) => r.timings.duration < 1000,
    'query has response body': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!querySuccess);
  
  if (!querySuccess) {
    console.log(`❌ Query failed: ${queryResponse.status}`);
  }
}

function testUploadEndpoint(headers) {
  let uploadResponse = http.post(`${BASE_URL}/documents/upload`, JSON.stringify({
    filename: `test_doc_${Math.random()}.pdf`,
    content_type: 'application/pdf',
    size: Math.floor(Math.random() * 10000000) + 1000000
  }), { headers });
  
  let uploadSuccess = check(uploadResponse, {
    'upload status is 200': (r) => r.status === 200,
    'upload response time < 2000ms': (r) => r.timings.duration < 2000,
    'upload has response': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!uploadSuccess);
  
  if (!uploadSuccess) {
    console.log(`❌ Upload failed: ${uploadResponse.status}`);
  }
}

function testListEndpoint(headers) {
  let listResponse = http.get(`${BASE_URL}/documents`, { headers });
  
  let listSuccess = check(listResponse, {
    'list status is 200': (r) => r.status === 200,
    'list response time < 500ms': (r) => r.timings.duration < 500,
    'list has array response': (r) => {
      try {
        return JSON.parse(r.body).documents.constructor === Array;
      } catch (e) {
        return false;
      }
    }
  });
  
  errorRate.add(!listSuccess);
  
  if (!listSuccess) {
    console.log(`❌ List failed: ${listResponse.status}`);
  }
}

function testModelsEndpoint(headers) {
  let modelsResponse = http.get(`${BASE_URL}/models`, { headers });
  
  let modelsSuccess = check(modelsResponse, {
    'models status is 200': (r) => r.status === 200,
    'models response time < 300ms': (r) => r.timings.duration < 300,
  });
  
  errorRate.add(!modelsSuccess);
}

function testHealthEndpoint() {
  let healthResponse = http.get(`${BASE_URL}/health`);
  
  let healthSuccess = check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 100ms': (r) => r.timings.duration < 100,
  });
  
  errorRate.add(!healthSuccess);
}

export function teardown() {
  console.log('✅ Simple load test completed');
  console.log('📈 Check results for performance analysis');
}
