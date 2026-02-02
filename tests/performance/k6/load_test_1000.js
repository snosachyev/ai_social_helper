// k6 Load Test Script for 1000+ Users
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
let errorRate = new Rate('errors');
let queryDuration = new Trend('query_duration');
let uploadDuration = new Trend('upload_duration');
let listDuration = new Trend('list_duration');

// Test configuration
export let options = {
  stages: [
    { duration: '2m', target: 100 },    // Warm up
    { duration: '3m', target: 300 },    // Ramp up to 300
    { duration: '5m', target: 500 },    // Ramp up to 500
    { duration: '5m', target: 800 },    // Ramp up to 800
    { duration: '5m', target: 1000 },   // Peak load 1000
    { duration: '10m', target: 1000 },  // Sustained load 1000
    { duration: '3m', target: 500 },    // Scale down
    { duration: '2m', target: 100 },    // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% under 500ms
    http_req_failed: ['rate<0.05'],      // Less than 5% errors
    errors: ['rate<0.05'],               // Custom error rate
    query_duration: ['p(95)<800'],      // Query specific threshold
    uploadDuration: ['p(95)<2000'],     // Upload specific threshold
  },
  throw: true,  // Stop on threshold breach
};

const BASE_URL = 'http://localhost';  // Update if needed
const TEST_QUERIES = [
  'What is machine learning?',
  'How does Redis work?',
  'Explain microservices architecture',
  'What are the benefits of PostgreSQL?',
  'How to optimize database performance?',
  'What is Docker and containerization?',
  'Explain load balancing concepts',
  'How does caching improve performance?',
  'What is API gateway pattern?',
  'Best practices for system design'
];

const TEST_DOCUMENTS = [
  { name: 'technical_doc.pdf', size: 5000000 },
  { name: 'user_manual.pdf', size: 3000000 },
  { name: 'specification.pdf', size: 8000000 },
  { name: 'guide.pdf', size: 2000000 },
  { name: 'documentation.pdf', size: 6000000 }
];

export function setup() {
  console.log('🚀 Starting 1000+ users load test...');
  console.log(`📊 Target: ${BASE_URL}`);
}

export default function() {
  let token = `test-load-token-${Math.floor(Math.random() * 1000) + 1}`;
  let headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Load-Test': 'true'
  };
  
  // Realistic endpoint distribution
  let endpoint = Math.random();
  
  if (endpoint < 0.40) {
    // 40% - Query requests (most expensive operation)
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
    // 10% - Health check (lightweight)
    testHealthEndpoint();
  }
  
  // Realistic think time between requests
  sleep(Math.random() * 3 + 1); // 1-4 seconds
}

function testQueryEndpoint(headers) {
  let query = TEST_QUERIES[Math.floor(Math.random() * TEST_QUERIES.length)];
  let startTime = Date.now();
  
  let queryResponse = http.post(`${BASE_URL}/query`, JSON.stringify({
    query: query,
    top_k: Math.floor(Math.random() * 5) + 3,
    retrieval_strategy: ['hybrid', 'semantic', 'keyword'][Math.floor(Math.random() * 3)],
    include_sources: Math.random() > 0.5
  }), { headers });
  
  let duration = Date.now() - startTime;
  queryDuration.add(duration);
  
  let querySuccess = check(queryResponse, {
    'query status is 200': (r) => r.status === 200,
    'query response time < 1000ms': (r) => r.timings.duration < 1000,
    'query has response body': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!querySuccess);
  
  if (!querySuccess) {
    console.log(`❌ Query failed: ${queryResponse.status} - ${queryResponse.body}`);
  }
}

function testUploadEndpoint(headers) {
  let doc = TEST_DOCUMENTS[Math.floor(Math.random() * TEST_DOCUMENTS.length)];
  let startTime = Date.now();
  
  // Simulate file upload with metadata
  let uploadResponse = http.post(`${BASE_URL}/documents/upload`, JSON.stringify({
    filename: `${Math.random().toString(36).substring(7)}_${doc.name}`,
    content_type: 'application/pdf',
    size: doc.size,
    upload_time: new Date().toISOString()
  }), { headers });
  
  let duration = Date.now() - startTime;
  uploadDuration.add(duration);
  
  let uploadSuccess = check(uploadResponse, {
    'upload status is 200': (r) => r.status === 200,
    'upload response time < 3000ms': (r) => r.timings.duration < 3000,
    'upload has response': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!uploadSuccess);
  
  if (!uploadSuccess) {
    console.log(`❌ Upload failed: ${uploadResponse.status} - ${uploadResponse.body}`);
  }
}

function testListEndpoint(headers) {
  let startTime = Date.now();
  
  let listResponse = http.get(`${BASE_URL}/documents`, { headers });
  
  let duration = Date.now() - startTime;
  listDuration.add(duration);
  
  let listSuccess = check(listResponse, {
    'list status is 200': (r) => r.status === 200,
    'list response time < 500ms': (r) => r.timings.duration < 500,
    'list has array response': (r) => {
      try {
        return JSON.parse(r.body).constructor === Array;
      } catch (e) {
        return false;
      }
    }
  });
  
  errorRate.add(!listSuccess);
  
  if (!listSuccess) {
    console.log(`❌ List failed: ${listResponse.status} - ${listResponse.body}`);
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
  console.log('✅ Load test completed');
  console.log('📈 Check results and metrics for performance analysis');
}
