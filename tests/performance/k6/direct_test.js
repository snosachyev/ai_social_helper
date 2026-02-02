import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const queryDuration = new Trend('query_duration');

// Test data
const testQueries = [
    "What is Python performance optimization?",
    "How to build scalable APIs with FastAPI?",
    "Python microservices architecture patterns",
    "RAG system with Python backend",
    "Async programming in Python"
];

// Test options - прямое подключение к Python
export const options = {
    stages: [
        { duration: '30s', target: 100 },   // Warm up
        { duration: '30s', target: 200 },   // Scale up
        { duration: '30s', target: 400 },   // Push to 400
        { duration: '30s', target: 600 },   // Push to 600
        { duration: '30s', target: 800 },   // Push to 800
        { duration: '30s', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<300'],
        http_req_failed: ['rate<0.2'],
        errors: ['rate<0.2'],
    },
};

export default function () {
    // Прямое подключение к Python API (без Nginx)
    const baseUrl = 'http://localhost:8000';
    
    // Тестируем только query endpoint для чистоты эксперимента
    const query = testQueries[Math.floor(Math.random() * testQueries.length)];
    const payload = JSON.stringify({
        query: query,
        top_k: Math.floor(Math.random() * 10) + 1,
        retrieval_strategy: 'hybrid',
        include_sources: Math.random() > 0.5
    });
    
    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': `req-${__VU}-${__ITER}`,
        },
    };
    
    const response = http.post(`${baseUrl}/query`, payload, params);
    const queryTime = response.timings.duration;
    
    queryDuration.add(queryTime);
    
    const checks = check(response, {
        'query status is 200': (r) => r.status === 200,
        'query response time < 300ms': (r) => r.timings.duration < 300,
        'query has response body': (r) => r.body && r.body.length > 0,
        'query has valid response': (r) => {
            try {
                const data = JSON.parse(r.body);
                return data.query && data.response;
            } catch (e) {
                return false;
            }
        },
    });
    
    errorRate.add(!checks);
    
    // Small sleep
    sleep(Math.random() * 0.1 + 0.05);
}

export function handleSummary(data) {
    console.log('\n🚀 Direct Python API Test Results (NO NGINX)');
    console.log('============================================');
    
    const totalRequests = data.metrics.http_reqs?.count || 0;
    const requestRate = data.metrics.http_reqs?.rate || 0;
    const avgResponseTime = data.metrics.http_req_duration?.avg || 0;
    const p95ResponseTime = data.metrics.http_req_duration?.['p(95)'] || 0;
    const errorRateValue = data.metrics.http_req_failed?.rate || 0;
    
    console.log(`✅ Total Requests: ${totalRequests}`);
    console.log(`📊 Request Rate: ${requestRate.toFixed(2)} req/s`);
    console.log(`⏱️  Average Response Time: ${avgResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P95 Response Time: ${p95ResponseTime.toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(errorRateValue * 100).toFixed(2)}%`);
    
    console.log('\n🎯 Analysis:');
    if (errorRateValue < 0.1) {
        console.log('✅ EXCELLENT: Python API handles load without Nginx!');
        console.log('🔥 Nginx is the bottleneck!');
    } else if (errorRateValue < 0.3) {
        console.log('⚠️  ACCEPTABLE: Some issues, but better than with Nginx');
        console.log('🔧 Nginx contributes to problems');
    } else {
        console.log('❌ POOR: Issues persist without Nginx');
        console.log('🔍 Problem is in Python/OS limits');
    }
    
    console.log('\n📊 Comparison with Nginx:');
    console.log('• If error rate < 20% here vs >90% with Nginx → Nginx problem');
    console.log('• If error rate similar → OS/Python problem');
    
    return {
        'direct_python_test': {
            total_requests: totalRequests,
            request_rate: requestRate,
            avg_response_time: avgResponseTime,
            p95_response_time: p95ResponseTime,
            error_rate: errorRateValue,
            nginx_bottleneck: errorRateValue < 0.2
        }
    };
}
