import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for Python 10-instances testing
const errorRate = new Rate('errors');
const queryDuration = new Trend('query_duration');
const documentsDuration = new Trend('documents_duration');
const modelsDuration = new Trend('models_duration');
const healthDuration = new Trend('health_duration');

// Test data for Python API
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

const testPrompts = [
    "Explain Python concurrency patterns",
    "Design a scalable API architecture",
    "Optimize database queries",
    "Implement caching strategies",
    "Build microservices with Python"
];

// Test options for 400 users (more realistic)
export const options = {
    stages: [
        { duration: '30s', target: 100 },   // Warm up to 100 users
        { duration: '30s', target: 200 },   // Scale to 200 users
        { duration: '60s', target: 400 },   // Scale to 400 users
        { duration: '60s', target: 400 },   // Hold at 400 users
        { duration: '30s', target: 200 },   // Scale down to 200
        { duration: '30s', target: 100 },   // Cool down to 100
        { duration: '30s', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<300'],    // 95% of requests under 300ms
        http_req_failed: ['rate<0.2'],       // Error rate under 20%
        errors: ['rate<0.2'],                // Custom error rate under 20%
        query_duration: ['p(95)<400'],       // Query responses under 400ms
        documents_duration: ['p(95)<200'],   // Documents responses under 200ms
        models_duration: ['p(95)<100'],      // Models responses under 100ms
    },
};

export default function () {
    const baseUrl = 'http://localhost:80';
    
    // Random endpoint selection for realistic traffic
    const endpointChoice = Math.random();
    
    if (endpointChoice < 0.4) {
        // 40% - Query endpoint (most common)
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
            'query response time < 400ms': (r) => r.timings.duration < 400,
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
        
    } else if (endpointChoice < 0.6) {
        // 20% - Documents endpoint
        const limit = Math.floor(Math.random() * 50) + 10;
        const offset = Math.floor(Math.random() * 100);
        
        const response = http.get(`${baseUrl}/documents?limit=${limit}&offset=${offset}`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const documentsTime = response.timings.duration;
        documentsDuration.add(documentsTime);
        
        const checks = check(response, {
            'documents status is 200': (r) => r.status === 200,
            'documents response time < 200ms': (r) => r.timings.duration < 200,
            'documents has array response': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return Array.isArray(data.documents);
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
        
    } else if (endpointChoice < 0.8) {
        // 20% - Models endpoint
        const response = http.get(`${baseUrl}/models`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const modelsTime = response.timings.duration;
        modelsDuration.add(modelsTime);
        
        const checks = check(response, {
            'models status is 200': (r) => r.status === 200,
            'models response time < 100ms': (r) => r.timings.duration < 100,
            'models has array response': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return Array.isArray(data.models);
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
        
    } else {
        // 20% - Health check
        const response = http.get(`${baseUrl}/health`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const healthTime = response.timings.duration;
        healthDuration.add(healthTime);
        
        const checks = check(response, {
            'health status is 200': (r) => r.status === 200,
            'health response time < 50ms': (r) => r.timings.duration < 50,
            'health has service_name': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return data.service_name === 'api-gateway-simple';
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
    }
    
    // Small sleep to simulate realistic user behavior
    sleep(Math.random() * 0.1 + 0.05); // 50-150ms
}

export function handleSummary(data) {
    console.log('\n🚀 Python 10-Instances (400 Users) Test Results');
    console.log('===============================================');
    
    // Safely access metrics with fallbacks
    const totalRequests = data.metrics.http_reqs?.count || 0;
    const requestRate = data.metrics.http_reqs?.rate || 0;
    const avgResponseTime = data.metrics.http_req_duration?.avg || 0;
    const p95ResponseTime = data.metrics.http_req_duration?.['p(95)'] || 0;
    const p99ResponseTime = data.metrics.http_req_duration?.['p(99)'] || 0;
    const errorRate = data.metrics.http_req_failed?.rate || 0;
    
    console.log(`✅ Total Requests: ${totalRequests}`);
    console.log(`📊 Request Rate: ${requestRate.toFixed(2)} req/s`);
    console.log(`⏱️  Average Response Time: ${avgResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P95 Response Time: ${p95ResponseTime.toFixed(2)}ms`);
    console.log(`🎯 P99 Response Time: ${p99ResponseTime.toFixed(2)}ms`);
    console.log(`❌ Error Rate: ${(errorRate * 100).toFixed(2)}%`);
    
    console.log('\n📈 Custom Metrics:');
    console.log(`🔍 Query P95: ${data.metrics.query_duration ? data.metrics.query_duration['p(95)'].toFixed(2) : 'N/A'}ms`);
    console.log(`📋 Documents P95: ${data.metrics.documents_duration ? data.metrics.documents_duration['p(95)'].toFixed(2) : 'N/A'}ms`);
    console.log(`🤖 Models P95: ${data.metrics.models_duration ? data.metrics.models_duration['p(95)'].toFixed(2) : 'N/A'}ms`);
    console.log(`❤️  Health P95: ${data.metrics.healthDuration ? data.metrics.healthDuration['p(95)'].toFixed(2) : 'N/A'}ms`);
    
    console.log('\n🎯 Performance Assessment:');
    if (errorRate < 0.1 && p95ResponseTime < 300) {
        console.log('✅ EXCELLENT: System handles 400 users with excellent performance!');
    } else if (errorRate < 0.2 && p95ResponseTime < 500) {
        console.log('✅ GOOD: System handles 400 users with acceptable performance');
    } else if (errorRate < 0.3 && p95ResponseTime < 1000) {
        console.log('⚠️  ACCEPTABLE: System works but needs optimization');
    } else {
        console.log('❌ POOR: System struggles under load');
    }
    
    console.log('\n🔧 Python 10-Instances Architecture:');
    console.log('   • 10x Python API Gateway instances');
    console.log('   • Nginx load balancer with optimized timeouts');
    console.log('   • PgBouncer connection pooling');
    console.log('   • PostgreSQL optimization');
    console.log('   • Redis caching');
    console.log('   • Rate limiting and connection pooling');
    
    // Performance rating
    let performanceRating = 'POOR';
    if (errorRate < 0.1 && p95ResponseTime < 300) {
        performanceRating = 'EXCELLENT';
    } else if (errorRate < 0.2 && p95ResponseTime < 500) {
        performanceRating = 'GOOD';
    } else if (errorRate < 0.3 && p95ResponseTime < 1000) {
        performanceRating = 'ACCEPTABLE';
    }
    
    console.log(`\n🏆 Overall Performance Rating: ${performanceRating}`);
    
    // Recommendations
    console.log('\n💡 Recommendations:');
    if (errorRate > 0.2) {
        console.log('   • Consider increasing number of API Gateway instances');
        console.log('   • Optimize rate limiting settings');
        console.log('   • Add more resources to containers');
    }
    if (p95ResponseTime > 300) {
        console.log('   • Optimize database queries');
        console.log('   • Implement better caching');
        console.log('   • Consider using faster storage');
    }
    if (performanceRating === 'EXCELLENT') {
        console.log('   • System is ready for production deployment');
        console.log('   • Consider testing with 500+ users');
        console.log('   • Monitor system resources under load');
    }
    
    return {
        'python_10_instances_400_test': {
            total_requests: totalRequests,
            request_rate: requestRate,
            avg_response_time: avgResponseTime,
            p95_response_time: p95ResponseTime,
            error_rate: errorRate,
            performance_rating: performanceRating
        }
    };
}
