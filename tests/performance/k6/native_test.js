import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

const testQueries = [
    "What is Python performance optimization?",
    "How to build scalable APIs with FastAPI?",
    "Python microservices architecture patterns",
    "RAG system with Python backend",
    "Async programming in Python"
];

// Тест нативного Python (без Docker)
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
    },
};

export default function () {
    // Нативный Python (без Docker)
    const baseUrl = 'http://localhost:8001';
    
    const query = testQueries[Math.floor(Math.random() * testQueries.length)];
    const payload = JSON.stringify({
        query: query,
        top_k: Math.floor(Math.random() * 10) + 1,
        retrieval_strategy: 'hybrid',
        include_sources: Math.random() > 0.5
    });
    
    const response = http.post(`${baseUrl}/query`, payload, {
        headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': `req-${__VU}-${__ITER}`,
        },
    });
    
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
    sleep(Math.random() * 0.1 + 0.05);
}

export function handleSummary(data) {
    const totalRequests = data.metrics.http_reqs?.count || 0;
    const requestRate = data.metrics.http_reqs?.rate || 0;
    const avgResponseTime = data.metrics.http_req_duration?.avg || 0;
    const p95ResponseTime = data.metrics.http_req_duration?.['p(95)'] || 0;
    const errorRateValue = data.metrics.http_req_failed?.rate || 0;
    
    console.log('\n🚀 Native Python Test Results (NO DOCKER)');
    console.log('==========================================');
    console.log(`✅ Total Requests: ${totalRequests}`);
    console.log(`📊 Request Rate: ${requestRate.toFixed(2)} req/s`);
    console.log(`⏱️  Average Response Time: ${avgResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P95 Response Time: ${p95ResponseTime.toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(errorRateValue * 100).toFixed(2)}%`);
    
    console.log('\n🎯 Docker vs Native Analysis:');
    if (errorRateValue < 0.1) {
        console.log('✅ SUCCESS: Native Python handles 800 users!');
        console.log('🔥 CONFIRMED: Docker networking is the bottleneck!');
        console.log('🐳 Docker userland proxy cannot handle 800+ concurrent connections');
    } else if (errorRateValue < 0.3) {
        console.log('⚠️  ACCEPTABLE: Native Python works better');
        console.log('🔧 Docker contributes to problems');
    } else {
        console.log('❌ PROBLEM: Issues persist even natively');
        console.log('🔍 Problem is in Python/OS, not Docker');
    }
    
    console.log('\n💡 Recommendations:');
    if (errorRateValue < 0.2) {
        console.log('✅ Use native Python for high-load testing');
        console.log('✅ Consider host networking in Docker');
        console.log('✅ Use Kubernetes (better networking)');
        console.log('❌ Avoid Docker Desktop for high-load testing');
    } else {
        console.log('🔧 Optimize Python uvicorn workers');
        console.log('🔧 Check system resource limits');
        console.log('🔧 Consider Go implementation');
    }
    
    return {
        'native_python_test': {
            total_requests: totalRequests,
            request_rate: requestRate,
            avg_response_time: avgResponseTime,
            p95_response_time: p95ResponseTime,
            error_rate: errorRateValue,
            docker_bottleneck: errorRateValue < 0.2
        }
    };
}
