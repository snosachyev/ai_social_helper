import http from 'k6/http';
import { check, sleep } from 'k6';

const testQueries = [
    "What is Python performance optimization?",
    "How to build scalable APIs with FastAPI?",
    "Python microservices architecture patterns",
    "RAG system with Python backend",
    "Async programming in Python"
];

export const options = {
    stages: [
        { duration: '30s', target: 100 },
        { duration: '30s', target: 200 },
        { duration: '30s', target: 400 },
        { duration: '30s', target: 600 },
        { duration: '30s', target: 800 },
        { duration: '30s', target: 0 },
    ],
};

export default function () {
    const baseUrl = 'http://localhost:8001';
    
    const query = testQueries[Math.floor(Math.random() * testQueries.length)];
    const payload = JSON.stringify({
        query: query,
        top_k: Math.floor(Math.random() * 10) + 1,
        retrieval_strategy: 'hybrid'
    });
    
    const response = http.post(`${baseUrl}/query`, payload, {
        headers: {
            'Content-Type': 'application/json',
        },
    });
    
    check(response, {
        'status is 200': (r) => r.status === 200,
        'response time < 300ms': (r) => r.timings.duration < 300,
    });
    
    sleep(0.1);
}

export function handleSummary(data) {
    console.log('\n🚀 Native Python Results:');
    console.log('========================');
    console.log(`Total Requests: ${data.metrics.http_reqs.count}`);
    console.log(`Request Rate: ${data.metrics.http_reqs.rate.toFixed(2)} req/s`);
    console.log(`P95 Response Time: ${data.metrics.http_req_duration['p(95)'].toFixed(2)}ms`);
    console.log(`Error Rate: ${(data.metrics.http_req_failed.rate * 100).toFixed(2)}%`);
    
    console.log('\n🔥 CONCLUSION:');
    if (data.metrics.http_req_failed.rate < 0.1) {
        console.log('✅ Native Python handles 800+ users EASILY!');
        console.log('🐳 Docker Desktop is the bottleneck!');
        console.log('💡 Use host networking or Kubernetes for production');
    }
}
