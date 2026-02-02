import http from 'k6/http';
import { check, sleep } from 'k6';

const testQueries = [
    "What is Python performance optimization?",
    "How to build scalable APIs with FastAPI?",
    "Python microservices architecture patterns",
    "RAG system with Python backend",
    "Async programming in Python",
    "API Gateway best practices",
    "Load balancing strategies",
    "Caching mechanisms in Python",
    "Database optimization techniques",
    "Redis performance tuning"
];

// Тест на 1000 пользователей с host networking
export const options = {
    stages: [
        { duration: '30s', target: 200 },   // Warm up
        { duration: '30s', target: 400 },   // Scale up
        { duration: '30s', target: 600 },   // Scale up
        { duration: '30s', target: 800 },   // Scale up
        { duration: '60s', target: 1000 },  // Peak load
        { duration: '30s', target: 600 },   // Scale down
        { duration: '30s', target: 200 },   // Cool down
        { duration: '30s', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<200'],    // 95% under 200ms
        http_req_failed: ['rate<0.05'],      // Error rate under 5%
    },
};

export default function () {
    // Используем Nginx load balancer на host networking
    const baseUrl = 'http://localhost:80';
    
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
        'status is 200': (r) => r.status === 200,
        'response time < 200ms': (r) => r.timings.duration < 200,
        'has response body': (r) => r.body && r.body.length > 0,
        'valid JSON response': (r) => {
            try {
                const data = JSON.parse(r.body);
                return data.query && data.response;
            } catch (e) {
                return false;
            }
        },
    });
    
    sleep(Math.random() * 0.1 + 0.05);
}

export function handleSummary(data) {
    console.log('\n🚀 Host Networking 1000 Users Test Results');
    console.log('===========================================');
    
    const totalRequests = data.metrics.http_reqs?.count || 0;
    const requestRate = data.metrics.http_reqs?.rate || 0;
    const avgResponseTime = data.metrics.http_req_duration?.avg || 0;
    const p95ResponseTime = data.metrics.http_req_duration?.['p(95)'] || 0;
    const p99ResponseTime = data.metrics.http_req_duration?.['p(99)'] || 0;
    const errorRate = data.metrics.http_req_failed?.rate || 0;
    
    console.log(`✅ Total Requests: ${totalRequests.toLocaleString()}`);
    console.log(`📊 Request Rate: ${requestRate.toFixed(2)} req/s`);
    console.log(`⏱️  Average Response Time: ${avgResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P95 Response Time: ${p95ResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P99 Response Time: ${p99ResponseTime.toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(errorRate * 100).toFixed(2)}%`);
    
    console.log('\n🎯 Performance Assessment:');
    if (errorRate < 0.05 && p95ResponseTime < 200) {
        console.log('🏆 EXCELLENT: Host networking handles 1000+ users perfectly!');
        console.log('✅ Docker networking problem SOLVED!');
        console.log('🚀 System is production-ready for 1000+ users!');
    } else if (errorRate < 0.1 && p95ResponseTime < 300) {
        console.log('✅ GOOD: Host networking works well with 1000 users');
        console.log('🔧 Minor optimizations needed for production');
    } else if (errorRate < 0.2 && p95ResponseTime < 500) {
        console.log('⚠️  ACCEPTABLE: Host networking improves but needs work');
        console.log('🔧 Consider more instances or optimization');
    } else {
        console.log('❌ POOR: Host networking still has issues');
        console.log('🔍 Need further investigation');
    }
    
    console.log('\n🔥 Host Networking vs Docker Bridge:');
    console.log(`• Bridge Networking: 90%+ errors (connection refused)`);
    console.log(`• Host Networking: ${(errorRate * 100).toFixed(2)}% errors`);
    console.log(`• Improvement: ${((90 - errorRate * 100) / 90 * 100).toFixed(1)}% reduction in errors`);
    
    console.log('\n💡 Production Recommendations:');
    if (errorRate < 0.1) {
        console.log('✅ DEPLOY TO PRODUCTION with host networking');
        console.log('✅ Add monitoring and alerting');
        console.log('✅ Consider Kubernetes for auto-scaling');
        console.log('✅ System ready for 1000+ concurrent users!');
    } else {
        console.log('🔧 Optimize uvicorn workers');
        console.log('🔧 Add more API Gateway instances');
        console.log('🔧 Consider Go implementation for higher performance');
    }
    
    return {
        'host_networking_1000_test': {
            total_requests: totalRequests,
            request_rate: requestRate,
            avg_response_time: avgResponseTime,
            p95_response_time: p95ResponseTime,
            p99_response_time: p99ResponseTime,
            error_rate: errorRate,
            success_rate: 1 - errorRate,
            performance_rating: errorRate < 0.05 ? 'EXCELLENT' : errorRate < 0.1 ? 'GOOD' : 'NEEDS_WORK'
        }
    };
}
