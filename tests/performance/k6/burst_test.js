import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for burst testing
export let errorRate = new Rate('errors');
export let burstLatency = new Trend('burst_latency');
export let concurrentRequests = new Trend('concurrent_requests');

// Heavy queries for burst testing
const HEAVY_QUERIES = [
    "Explain the complete architecture of transformer models including attention mechanisms, positional encoding, and multi-head attention",
    "Compare and contrast different optimization algorithms used in deep learning including SGD, Adam, RMSprop with mathematical formulations",
    "Provide a comprehensive analysis of bias and fairness issues in large language models including detection methods and mitigation strategies",
    "Describe the complete pipeline for building production-ready ML systems including data preprocessing, model training, deployment, and monitoring",
    "Explain quantum computing applications in machine learning including quantum neural networks and quantum optimization algorithms"
];

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export let options = {
    stages: [
        { duration: '30s', target: 100 },  // Quick ramp up
        { duration: '30s', target: 1000 }, // Burst phase - 1000 concurrent
        { duration: '4m', target: 0 },    // Gradual ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<5000'], // More lenient for burst
        http_req_failed: ['rate<0.05'],     // Allow 5% errors during burst
        errors: ['rate<0.05'],
        burst_latency: ['p(95)<5000'],
    },
    scenarios: {
        burst_scenario: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '30s', target: 100 },
                { duration: '30s', target: 1000 }, // Main burst
                { duration: '4m', target: 0 },
            ],
            gracefulRampDown: '10s',
        },
    },
};

export function setup() {
    console.log('Starting BURST load test - 1000 requests in 30 seconds');
    console.log(`Target URL: ${BASE_URL}`);
    console.log('WARNING: This will generate extreme load on the system');
}

export default function() {
    // All requests are heavy RAG operations during burst
    performHeavyQuery();
    
    // Minimal sleep during burst
    sleep(0.1);
}

function performHeavyQuery() {
    const payload = {
        query: HEAVY_QUERIES[Math.floor(Math.random() * HEAVY_QUERIES.length)],
        top_k: 10, // Maximum results
        retrieval_strategy: "comprehensive",
        include_sources: true,
        include_explanations: true,
        max_context_length: 4000,
        temperature: 0.1,
        stream: false
    };
    
    const startTime = Date.now();
    
    // Track concurrent requests
    concurrentRequests.add(__ENV.VUS || 1);
    
    const response = http.post(`${BASE_URL}/api/v1/query`, JSON.stringify(payload), {
        headers: {
            'Authorization': `Bearer burst-test-${Math.random().toString(36).substr(2, 9)}`,
            'Content-Type': 'application/json',
            'X-Test-Type': 'burst'
        },
        timeout: '15s' // Longer timeout for complex queries
    });
    
    const endTime = Date.now();
    burstLatency.add(endTime - startTime);
    
    const success = check(response, {
        'burst query status is 200': (r) => r.status === 200,
        'burst query response time < 5s': (r) => r.timings.duration < 5000,
        'burst query has comprehensive results': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.results && 
                       body.results.length > 0 && 
                       body.sources && 
                       body.explanations;
            } catch (e) {
                return false;
            }
        },
        'burst query not rate limited': (r) => r.status !== 429,
        'burst query not timed out': (r) => r.status !== 504,
    });
    
    if (!success) {
        errorRate.add(1);
        
        // Log specific failure types during burst
        if (response.status === 429) {
            console.log('RATE LIMIT HIT during burst');
        } else if (response.status === 503) {
            console.log('SERVICE UNAVAILABLE during burst');
        } else if (response.timings.duration > 5000) {
            console.log('TIMEOUT during burst - slow response');
        } else {
            console.log(`Burst query failed: ${response.status} - ${response.body.substring(0, 200)}`);
        }
    } else {
        errorRate.add(0);
    }
}

export function teardown(data) {
    console.log('Burst test completed');
    console.log(`Final error rate: ${errorRate.rate * 100}%`);
    console.log(`Average burst latency: ${burstLatency.avg}ms`);
    console.log(`P95 burst latency: ${burstLatency.p(95)}ms`);
    console.log(`Max concurrent requests: ${concurrentRequests.max}`);
    
    // Additional burst-specific metrics
    if (errorRate.rate > 0.05) {
        console.warn('HIGH ERROR RATE during burst - system may be overloaded');
    }
    
    if (burstLatency.p(95) > 5000) {
        console.warn('HIGH LATENCY during burst - performance degradation detected');
    }
}
