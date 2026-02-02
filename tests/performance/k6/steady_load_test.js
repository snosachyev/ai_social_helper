import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');
export let queryLatency = new Trend('query_latency');
export let uploadLatency = new Trend('upload_latency');
export let searchLatency = new Trend('search_latency');

// Test data
const QUERIES = [
    "What is machine learning?",
    "How does neural network work?",
    "Explain deep learning concepts",
    "What are transformers in AI?",
    "How to optimize model performance?",
    "What is reinforcement learning?",
    "Explain computer vision",
    "How do GPT models work?",
    "What is natural language processing?",
    "How to train AI models?"
];

const DOCUMENTS = [
    'ml_basics.pdf',
    'deep_learning.pdf', 
    'neural_networks.pdf',
    'ai_ethics.pdf',
    'data_science.pdf'
];

// Base URL configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Authentication setup
function getAuthHeaders() {
    // Simulate JWT token or API key
    return {
        'Authorization': `Bearer test-token-${Math.random().toString(36).substr(2, 9)}`,
        'Content-Type': 'application/json'
    };
}

export let options = {
    stages: [
        { duration: '2m', target: 100 },   // Ramp up
        { duration: '26m', target: 1000 }, // Steady state
        { duration: '2m', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<3000'], // 95% under 3s
        http_req_failed: ['rate<0.01'],     // <1% errors
        errors: ['rate<0.01'],
        query_latency: ['p(95)<3000'],
        upload_latency: ['p(95)<10000'],
        search_latency: ['p(95)<2000'],
    },
    ext: {
        loadimpact: {
            projectID: 123456,
            name: 'RAG System Steady Load Test'
        }
    }
};

export function setup() {
    console.log('Starting steady load test for RAG system');
    console.log(`Target URL: ${BASE_URL}`);
    console.log('Expected concurrent users: 1000');
}

export default function() {
    // Randomly select operation based on distribution
    const rand = Math.random();
    
    if (rand < 0.4) {
        // 40% - Query operations
        performQuery();
    } else if (rand < 0.65) {
        // 25% - Document upload
        performDocumentUpload();
    } else if (rand < 0.85) {
        // 20% - Document search
        performDocumentSearch();
    } else {
        // 15% - Health checks
        performHealthCheck();
    }
    
    // Sleep between requests (1-3 seconds)
    sleep(Math.random() * 2 + 1);
}

function performQuery() {
    const payload = {
        query: QUERIES[Math.floor(Math.random() * QUERIES.length)],
        top_k: Math.floor(Math.random() * 5) + 3,
        retrieval_strategy: "hybrid",
        include_sources: true
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/query`, JSON.stringify(payload), {
        headers: getAuthHeaders(),
        timeout: '10s'
    });
    
    const endTime = Date.now();
    queryLatency.add(endTime - startTime);
    
    const success = check(response, {
        'query status is 200': (r) => r.status === 200,
        'query response time < 3s': (r) => r.timings.duration < 3000,
        'query has results': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.results && body.results.length > 0;
            } catch (e) {
                return false;
            }
        }
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Query failed: ${response.status} - ${response.body}`);
    } else {
        errorRate.add(0);
    }
}

function performDocumentUpload() {
    // Simulate document upload with metadata
    const payload = {
        filename: DOCUMENTS[Math.floor(Math.random() * DOCUMENTS.length)],
        content_type: "application/pdf",
        size: Math.floor(Math.random() * 10000000) + 1000000, // 1MB-10MB
        metadata: {
            category: "technical",
            language: "en",
            tags: ["ai", "ml", "research"]
        }
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/documents/upload`, JSON.stringify(payload), {
        headers: getAuthHeaders(),
        timeout: '30s'
    });
    
    const endTime = Date.now();
    uploadLatency.add(endTime - startTime);
    
    const success = check(response, {
        'upload status is 200 or 202': (r) => r.status === 200 || r.status === 202,
        'upload response time < 10s': (r) => r.timings.duration < 10000,
        'upload has document_id': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.document_id;
            } catch (e) {
                return false;
            }
        }
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Upload failed: ${response.status} - ${response.body}`);
    } else {
        errorRate.add(0);
    }
}

function performDocumentSearch() {
    const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];
    const payload = {
        query: query,
        limit: Math.floor(Math.random() * 10) + 5,
        filters: {
            category: "technical",
            language: "en"
        }
    };
    
    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/api/v1/documents/search`, JSON.stringify(payload), {
        headers: getAuthHeaders(),
        timeout: '5s'
    });
    
    const endTime = Date.now();
    searchLatency.add(endTime - startTime);
    
    const success = check(response, {
        'search status is 200': (r) => r.status === 200,
        'search response time < 2s': (r) => r.timings.duration < 2000,
        'search has results': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.documents && body.documents.length > 0;
            } catch (e) {
                return false;
            }
        }
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Search failed: ${response.status} - ${response.body}`);
    } else {
        errorRate.add(0);
    }
}

function performHealthCheck() {
    const response = http.get(`${BASE_URL}/health`, {
        headers: getAuthHeaders(),
        timeout: '2s'
    });
    
    const success = check(response, {
        'health status is 200': (r) => r.status === 200,
        'health response time < 1s': (r) => r.timings.duration < 1000,
        'health shows healthy': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.status === 'healthy';
            } catch (e) {
                return false;
            }
        }
    });
    
    if (!success) {
        errorRate.add(1);
        console.log(`Health check failed: ${response.status} - ${response.body}`);
    } else {
        errorRate.add(0);
    }
}

export function teardown(data) {
    console.log('Steady load test completed');
    console.log(`Final error rate: ${errorRate.rate * 100}%`);
    console.log(`Average query latency: ${queryLatency.avg}ms`);
    console.log(`Average upload latency: ${uploadLatency.avg}ms`);
    console.log(`Average search latency: ${searchLatency.avg}ms`);
}
