import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
    stages: [
        { duration: '10s', target: 50 },
        { duration: '20s', target: 100 },
        { duration: '20s', target: 200 },
        { duration: '10s', target: 0 },
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.1'],
    },
};

export default function () {
    let responses = [
        http.get('http://localhost:80/health'),
        http.post('http://localhost:80/query', JSON.stringify({
            query: 'test query',
            top_k: 5
        }), {
            headers: { 'Content-Type': 'application/json' }
        }),
        http.get('http://localhost:80/documents'),
        http.get('http://localhost:80/models'),
    ];

    check(responses[0], {
        'health status is 200': (r) => r.status === 200,
    });

    check(responses[1], {
        'query status is 200': (r) => r.status === 200,
        'query response time < 500ms': (r) => r.timings.duration < 500,
    });

    check(responses[2], {
        'documents status is 200': (r) => r.status === 200,
    });

    check(responses[3], {
        'models status is 200': (r) => r.status === 200,
    });

    sleep(0.1);
}

export function handleSummary(data) {
    console.log('\n🚀 Simple Go API Test Results');
    console.log('==============================');
    console.log(`✅ Total Requests: ${data.metrics.http_reqs.count}`);
    console.log(`📊 Request Rate: ${data.metrics.http_reqs.rate.toFixed(2)} req/s`);
    console.log(`⏱️  P95 Response Time: ${data.metrics.http_req_duration['p(95)'].toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(data.metrics.http_req_failed.rate * 100).toFixed(2)}%`);
    
    if (data.metrics.http_req_failed.rate < 0.1) {
        console.log('✅ GOOD: System performs well under load');
    } else {
        console.log('⚠️  NEEDS OPTIMIZATION: High error rate detected');
    }
}
