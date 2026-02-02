import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

const testQueries = [
    "What is Python performance optimization?",
    "How to build scalable APIs with FastAPI?",
    "Python microservices architecture patterns"
];

// Тестируем с меньшей нагрузкой
export const options = {
    stages: [
        { duration: '30s', target: 50 },    // Только 50 пользователей
        { duration: '30s', target: 100 },   // Увеличим до 100
        { duration: '30s', target: 150 },   // Увеличим до 150
        { duration: '30s', target: 200 },   // Увеличим до 200
        { duration: '30s', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<300'],
        http_req_failed: ['rate<0.3'],
    },
};

export default function () {
    const baseUrl = 'http://localhost:8000';
    
    const query = testQueries[Math.floor(Math.random() * testQueries.length)];
    const payload = JSON.stringify({
        query: query,
        top_k: 5,
        retrieval_strategy: 'hybrid'
    });
    
    const response = http.post(`${baseUrl}/query`, payload, {
        headers: {
            'Content-Type': 'application/json',
        },
    });
    
    const checks = check(response, {
        'query status is 200': (r) => r.status === 200,
        'query response time < 300ms': (r) => r.timings.duration < 300,
        'query has response body': (r) => r.body && r.body.length > 0,
    });
    
    errorRate.add(!checks);
    sleep(0.1);
}

export function handleSummary(data) {
    const totalRequests = data.metrics.http_reqs?.count || 0;
    const requestRate = data.metrics.http_reqs?.rate || 0;
    const p95ResponseTime = data.metrics.http_req_duration?.['p(95)'] || 0;
    const errorRateValue = data.metrics.http_req_failed?.rate || 0;
    
    console.log('\n🚀 Direct Python API Test (Small Load)');
    console.log('=======================================');
    console.log(`✅ Total Requests: ${totalRequests}`);
    console.log(`📊 Request Rate: ${requestRate.toFixed(2)} req/s`);
    console.log(`🎯 P95 Response Time: ${p95ResponseTime.toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(errorRateValue * 100).toFixed(2)}%`);
    
    if (errorRateValue < 0.1) {
        console.log('✅ SUCCESS: Python API handles load well!');
    } else if (errorRateValue < 0.3) {
        console.log('⚠️  ACCEPTABLE: Some issues');
    } else {
        console.log('❌ PROBLEM: High error rate');
    }
    
    console.log('\n🔍 Next steps:');
    if (errorRateValue < 0.3) {
        console.log('• Try increasing to 400 users');
        console.log('• Check uvicorn worker limits');
        console.log('• Monitor container resources');
    } else {
        console.log('• Check container logs');
        console.log('• Verify uvicorn configuration');
        console.log('• Consider Go implementation');
    }
}
