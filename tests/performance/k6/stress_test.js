// k6 Stress Test - Push System to Limits
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for stress testing
let errorRate = new Rate('errors');
let systemLoad = new Trend('system_load');
let responseTimeP99 = new Trend('response_time_p99');

export let options = {
  stages: [
    { duration: '1m', target: 500 },     // Quick ramp to 500
    { duration: '2m', target: 1000 },    // Ramp to 1000
    { duration: '3m', target: 1500 },    // Push to 1500
    { duration: '3m', target: 2000 },    // Push to 2000 (stress)
    { duration: '2m', target: 2500 },    // Maximum stress
    { duration: '5m', target: 2500 },    // Sustain maximum load
    { duration: '2m', target: 1000 },    // Recovery
    { duration: '1m', target: 0 },       // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],   // More lenient for stress test
    http_req_failed: ['rate<0.10'],      // Allow 10% errors under stress
    errors: ['rate<0.10'],
  },
  throw: false,  // Don't stop on threshold breach for stress test
};

const BASE_URL = 'http://localhost';
const HEAVY_QUERIES = [
  'Explain in detail the architecture of distributed systems including all components and their interactions',
  'Provide comprehensive analysis of database optimization techniques for large-scale applications',
  'What are all the best practices for microservices including design patterns, deployment strategies, and monitoring?',
  'Complete guide to container orchestration with Kubernetes including networking, storage, and security',
  'How to design and implement a scalable API gateway with rate limiting, authentication, and load balancing'
];

export function setup() {
  console.log('🔥 Starting stress test - pushing system to limits!');
}

export default function() {
  let token = `stress-test-token-${Math.floor(Math.random() * 2000) + 1}`;
  let headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Load-Test': 'true',
    'X-Stress-Test': 'true'
  };
  
  // Stress test distribution - focus on heavy operations
  let endpoint = Math.random();
  
  if (endpoint < 0.60) {
    // 60% - Heavy queries (most resource intensive)
    testHeavyQuery(headers);
    
  } else if (endpoint < 0.80) {
    // 20% - Rapid document operations
    testRapidOperations(headers);
    
  } else if (endpoint < 0.95) {
    // 15% - Model operations
    testModelOperations(headers);
    
  } else {
    // 5% - Health checks during stress
    testHealthUnderStress();
  }
  
  // Reduced think time for stress test
  sleep(Math.random() * 1 + 0.5); // 0.5-1.5 seconds
}

function testHeavyQuery(headers) {
  let query = HEAVY_QUERIES[Math.floor(Math.random() * HEAVY_QUERIES.length)];
  let startTime = Date.now();
  
  let queryResponse = http.post(`${BASE_URL}/query`, JSON.stringify({
    query: query,
    top_k: Math.floor(Math.random() * 10) + 5, // Larger top_k for stress
    retrieval_strategy: 'hybrid',
    include_sources: true,
    include_metadata: true,
    max_context_length: 4000 // Larger context
  }), { headers });
  
  let duration = Date.now() - startTime;
  systemLoad.add(duration);
  responseTimeP99.add(duration);
  
  let success = check(queryResponse, {
    'query status is 200 or 429': (r) => r.status === 200 || r.status === 429, // Allow rate limiting
    'query response time < 5000ms': (r) => r.timings.duration < 5000,
  });
  
  errorRate.add(!success);
  
  if (queryResponse.status === 429) {
    console.log('⚠️ Rate limited - system protecting itself');
  } else if (queryResponse.status >= 500) {
    console.log(`❌ Server error under stress: ${queryResponse.status}`);
  }
}

function testRapidOperations(headers) {
  // Rapid document list and upload simulation
  let operations = Math.random();
  
  if (operations < 0.5) {
    // Rapid document listing
    let listResponse = http.get(`${BASE_URL}/documents?limit=100&offset=${Math.floor(Math.random() * 50)}`, { headers });
    
    check(listResponse, {
      'list status acceptable': (r) => r.status < 500,
    });
    
  } else {
    // Rapid upload simulation
    let uploadResponse = http.post(`${BASE_URL}/documents/upload`, JSON.stringify({
      filename: `stress_${Date.now()}_${Math.random().toString(36).substring(7)}.pdf`,
      content_type: 'application/pdf',
      size: Math.floor(Math.random() * 10000000) + 1000000, // 1-10MB
      priority: 'high'
    }), { headers });
    
    check(uploadResponse, {
      'upload status acceptable': (r) => r.status < 500,
    });
  }
}

function testModelOperations(headers) {
  // Test model listing and loading
  let modelOp = Math.random();
  
  if (modelOp < 0.7) {
    // List models
    let modelsResponse = http.get(`${BASE_URL}/models`, { headers });
    
    check(modelsResponse, {
      'models status acceptable': (r) => r.status < 500,
    });
    
  } else {
    // Attempt model load (may fail under stress)
    let loadResponse = http.post(`${BASE_URL}/models/test-model/load`, JSON.stringify({
      force_reload: false
    }), { headers });
    
    check(loadResponse, {
      'model load status acceptable': (r) => r.status < 500,
    });
  }
}

function testHealthUnderStress() {
  let healthResponse = http.get(`${BASE_URL}/health`);
  
  let healthSuccess = check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  if (!healthSuccess) {
    console.log(`🚨 Health check failing under stress: ${healthResponse.status}`);
  }
}

export function teardown() {
  console.log('🔥 Stress test completed!');
  console.log('📊 Analyze system behavior under extreme load');
  console.log('🔍 Check for bottlenecks, memory leaks, and failure points');
}
