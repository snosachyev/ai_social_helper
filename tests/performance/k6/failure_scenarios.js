import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Failure scenario specific metrics
export let errorRate = new Rate('errors');
export let circuitBreakerTrips = new Counter('circuit_breaker_trips');
export let fallbackResponses = new Counter('fallback_responses');
export let serviceFailureLatency = new Trend('service_failure_latency');
export let recoveryTime = new Trend('recovery_time');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const FAILURE_SCENARIO = __ENV.FAILURE_SCENARIO || 'embedding-service';

// Test queries
const QUERIES = [
    "What is machine learning?",
    "How do neural networks work?",
    "Explain deep learning"
];

export let options = {
    stages: [
        { duration: '2m', target: 200 },   // Warm up
        { duration: '10m', target: 800 },   // Load during failure
        { duration: '3m', target: 0 },     // Cool down
    ],
    thresholds: {
        http_req_duration: ['p(95)<10000'], // More lenient during failures
        http_req_failed: ['rate<0.15'],     // Allow higher error rate
        errors: ['rate<0.15'],
    },
};

export function setup() {
    console.log(`Starting FAILURE SCENARIO test: ${FAILURE_SCENARIO}`);
    console.log('This test simulates service failures and tests resilience');
    
    // Inject failure based on scenario
    injectFailure();
}

export default function() {
    switch (FAILURE_SCENARIO) {
        case 'embedding-service':
            testEmbeddingServiceFailure();
            break;
        case 'generation-service':
            testGenerationServiceFailure();
            break;
        case 'vector-store':
            testVectorStoreFailure();
            break;
        case 'database':
            testDatabaseFailure();
            break;
        default:
            testGeneralFailure();
    }
    
    sleep(Math.random() * 2 + 1);
}

function testEmbeddingServiceFailure() {
    // Test queries that require embedding generation
    const payload = {
        query: QUERIES[Math.floor(Math.random() * QUERIES.length)],
        top_k: 5,
        retrieval_strategy: "vector_search" // Requires embedding
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/query`, JSON.stringify(payload), {
        headers: {
            'Authorization': `Bearer test-${Math.random().toString(36).substr(2, 9)}`,
            'Content-Type': 'application/json',
            'X-Failure-Scenario': 'embedding-service'
        },
        timeout: '15s'
    });
    
    const endTime = Date.now();
    serviceFailureLatency.add(endTime - startTime);
    
    const success = check(response, {
        'query handled gracefully': (r) => {
            // Should either succeed or fail gracefully
            return r.status === 200 || 
                   r.status === 503 || 
                   r.status === 202 || // Accepted with fallback
                   r.status === 429;   // Rate limited
        },
        'no server errors': (r) => r.status !== 500,
        'response time reasonable': (r) => r.timings.duration < 15000,
    });
    
    // Check for fallback responses
    if (response.status === 202) {
        fallbackResponses.add(1);
        console.log('Fallback response detected - embedding service failed');
    }
    
    // Check for circuit breaker activation
    if (response.status === 503 && response.body.includes('circuit breaker')) {
        circuitBreakerTrips.add(1);
        console.log('Circuit breaker activated for embedding service');
    }
    
    if (!success) {
        errorRate.add(1);
        console.log(`Embedding failure test failed: ${response.status}`);
    } else {
        errorRate.add(0);
    }
}

function testGenerationServiceFailure() {
    // Test queries that require LLM generation
    const payload = {
        query: QUERIES[Math.floor(Math.random() * QUERIES.length)],
        top_k: 3,
        generate_response: true,
        max_tokens: 500
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/generate`, JSON.stringify(payload), {
        headers: {
            'Authorization': `Bearer test-${Math.random().toString(36).substr(2, 9)}`,
            'Content-Type': 'application/json',
            'X-Failure-Scenario': 'generation-service'
        },
        timeout: '20s'
    });
    
    const endTime = Date.now();
    serviceFailureLatency.add(endTime - startTime);
    
    const success = check(response, {
        'generation handled gracefully': (r) => {
            return r.status === 200 || 
                   r.status === 503 || 
                   r.status === 202 || // Cached response
                   r.status === 408;   // Timeout
        },
        'no server errors': (r) => r.status !== 500,
        'response time reasonable': (r) => r.timings.duration < 20000,
    });
    
    // Check for cached fallback
    if (response.status === 202) {
        fallbackResponses.add(1);
        console.log('Cached fallback response detected - generation service failed');
    }
    
    if (!success) {
        errorRate.add(1);
        console.log(`Generation failure test failed: ${response.status}`);
    } else {
        errorRate.add(0);
    }
}

function testVectorStoreFailure() {
    // Test vector search operations
    const payload = {
        query: QUERIES[Math.floor(Math.random() * QUERIES.length)],
        top_k: 5,
        retrieval_strategy: "vector_only"
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/search`, JSON.stringify(payload), {
        headers: {
            'Authorization': `Bearer test-${Math.random().toString(36).substr(2, 9)}`,
            'Content-Type': 'application/json',
            'X-Failure-Scenario': 'vector-store'
        },
        timeout: '10s'
    });
    
    const endTime = Date.now();
    serviceFailureLatency.add(endTime - startTime);
    
    const success = check(response, {
        'vector search handled gracefully': (r) => {
            return r.status === 200 || 
                   r.status === 503 || 
                   r.status === 404 ||  // Index unavailable
                   r.status === 503;   // Service unavailable
        },
        'no server errors': (r) => r.status !== 500,
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Vector store failure test failed: ${response.status}`);
    } else {
        errorRate.add(0);
    }
}

function testDatabaseFailure() {
    // Test operations requiring database access
    const response = http.get(`${BASE_URL}/api/v1/documents`, {
        headers: {
            'Authorization': `Bearer test-${Math.random().toString(36).substr(2, 9)}`,
            'X-Failure-Scenario': 'database'
        },
        timeout: '10s'
    });
    
    const success = check(response, {
        'database operation handled gracefully': (r) => {
            return r.status === 200 || 
                   r.status === 503 || 
                   r.status === 504;   // Gateway timeout
        },
        'no server errors': (r) => r.status !== 500,
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Database failure test failed: ${response.status}`);
    } else {
        errorRate.add(0);
    }
}

function testGeneralFailure() {
    // General resilience test
    const operations = [
        () => http.get(`${BASE_URL}/health`),
        () => http.get(`${BASE_URL}/api/v1/status`),
        () => http.post(`${BASE_URL}/api/v1/query`, JSON.stringify({
            query: "test query",
            top_k: 3
        }), {
            headers: { 'Content-Type': 'application/json' }
        })
    ];
    
    const operation = operations[Math.floor(Math.random() * operations.length)];
    const response = operation();
    
    const success = check(response, {
        'system responds': (r) => r.status < 500,
        'no crashes': (r) => r.status !== 500,
    });
    
    if (!success) {
        errorRate.add(1);
    } else {
        errorRate.add(0);
    }
}

function injectFailure() {
    // This would normally trigger actual service failures
    // For testing purposes, we simulate through headers
    console.log(`Injecting failure for: ${FAILURE_SCENARIO}`);
    
    // In real implementation, this could:
    // - Call admin API to disable service
    // - Stop containers via Docker API
    // - Network partitioning
    // - Resource exhaustion
}

export function teardown(data) {
    console.log('Failure scenario test completed');
    console.log(`Tested scenario: ${FAILURE_SCENARIO}`);
    console.log(`Final error rate: ${errorRate.rate * 100}%`);
    console.log(`Circuit breaker trips: ${circuitBreakerTrips.count}`);
    console.log(`Fallback responses: ${fallbackResponses.count}`);
    console.log(`Average latency during failure: ${serviceFailureLatency.avg}ms`);
    
    // Recovery assessment
    if (errorRate.rate < 0.15) {
        console.log('✅ System handled failure gracefully');
    } else {
        console.warn('❌ System did not handle failure well');
    }
    
    if (circuitBreakerTrips.count > 0) {
        console.log('⚡ Circuit breaker was activated - good resilience pattern');
    }
    
    if (fallbackResponses.count > 0) {
        console.log('🔄 Fallback mechanisms were used - system degraded gracefully');
    }
}
