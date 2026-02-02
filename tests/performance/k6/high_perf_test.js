import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for high-performance testing
const errorRate = new Rate('errors');
const queryDuration = new Trend('query_duration');
const uploadDuration = new Trend('upload_duration');
const listDuration = new Trend('list_duration');
const generateDuration = new Trend('generate_duration');
const healthDuration = new Trend('health_duration');

// Test data for high-performance Go API
const testQueries = [
    "What is Go performance optimization?",
    "How to build high-performance APIs?",
    "Go microservices architecture patterns",
    "RAG system with Go backend",
    "Concurrent programming in Go",
    "API Gateway best practices",
    "Load balancing strategies",
    "Caching mechanisms in Go",
    "Database optimization techniques",
    "Redis performance tuning"
];

const testPrompts = [
    "Explain Go concurrency patterns",
    "Design a scalable API architecture",
    "Optimize database queries",
    "Implement caching strategies",
    "Build microservices with Go"
];

// Test options for 1000+ users
export const options = {
    stages: [
        { duration: '30s', target: 500 },   // Warm up to 500 users
        { duration: '30s', target: 1000 },  // Scale to 1000 users
        { duration: '60s', target: 1500 },  // Push to 1500 users
        { duration: '60s', target: 2000 },  // Target 2000 users
        { duration: '30s', target: 1000 },  // Scale down to 1000
        { duration: '30s', target: 500 },   // Cool down to 500
        { duration: '30s', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<200'],    // 95% of requests under 200ms
        http_req_failed: ['rate<0.05'],      // Error rate under 5%
        errors: ['rate<0.05'],               // Custom error rate under 5%
        query_duration: ['p(95)<300'],       // Query responses under 300ms
        list_duration: ['p(95)<100'],        // List responses under 100ms
        generate_duration: ['p(95)<400'],     // Generate responses under 400ms
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
            'query response time < 300ms': (r) => r.timings.duration < 300,
            'query has response body': (r) => r.body && r.body.length > 0,
            'query has sources': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return data.sources && data.sources.length > 0;
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
        
    } else if (endpointChoice < 0.6) {
        // 20% - Generate endpoint
        const prompt = testPrompts[Math.floor(Math.random() * testPrompts.length)];
        const payload = JSON.stringify({
            prompt: prompt
        });
        
        const params = {
            headers: {
                'Content-Type': 'application/json',
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        };
        
        const response = http.post(`${baseUrl}/generate`, payload, params);
        const generateTime = response.timings.duration;
        
        generateDuration.add(generateTime);
        
        const checks = check(response, {
            'generate status is 200': (r) => r.status === 200,
            'generate response time < 400ms': (r) => r.timings.duration < 400,
            'generate has response': (r) => r.body && r.body.length > 0,
            'generate has tokens_used': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return data.tokens_used > 0;
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
        
    } else if (endpointChoice < 0.8) {
        // 20% - Documents list
        const limit = Math.floor(Math.random() * 50) + 10;
        const offset = Math.floor(Math.random() * 100);
        
        const response = http.get(`${baseUrl}/documents?limit=${limit}&offset=${offset}`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const listTime = response.timings.duration;
        listDuration.add(listTime);
        
        const checks = check(response, {
            'list status is 200': (r) => r.status === 200,
            'list response time < 100ms': (r) => r.timings.duration < 100,
            'list has array response': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return Array.isArray(data.documents);
                } catch (e) {
                    return false;
                }
            },
        });
        
        errorRate.add(!checks);
        
    } else if (endpointChoice < 0.95) {
        // 15% - Models endpoint
        const response = http.get(`${baseUrl}/models`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const checks = check(response, {
            'models status is 200': (r) => r.status === 200,
            'models response time < 50ms': (r) => r.timings.duration < 50,
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
        // 5% - Health check
        const response = http.get(`${baseUrl}/health`, {
            headers: {
                'X-Request-ID': `req-${__VU}-${__ITER}`,
            },
        });
        
        const healthTime = response.timings.duration;
        healthDuration.add(healthTime);
        
        const checks = check(response, {
            'health status is 200': (r) => r.status === 200,
            'health response time < 20ms': (r) => r.timings.duration < 20,
            'health has service_name': (r) => {
                try {
                    const data = JSON.parse(r.body);
                    return data.service_name === 'api-gateway-go';
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
    console.log('\n🚀 High-Performance Go API Gateway Test Results');
    console.log('================================================');
    
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
    console.log(`⚡ Generate P95: ${data.metrics.generate_duration ? data.metrics.generate_duration['p(95)'].toFixed(2) : 'N/A'}ms`);
    console.log(`📋 List P95: ${data.metrics.list_duration ? data.metrics.list_duration['p(95)'].toFixed(2) : 'N/A'}ms`);
    console.log(`❤️  Health P95: ${data.metrics.healthDuration ? data.metrics.healthDuration['p(95)'].toFixed(2) : 'N/A'}ms`);
    
    console.log('\n🎯 Performance Assessment:');
    if (errorRate < 0.05 && p95ResponseTime < 200) {
        console.log('✅ EXCELLENT: System handles 1000+ users with excellent performance!');
    } else if (errorRate < 0.1 && p95ResponseTime < 500) {
        console.log('✅ GOOD: System handles high load with acceptable performance');
    } else {
        console.log('⚠️  NEEDS OPTIMIZATION: System struggles under high load');
    }
    
    console.log('\n🔧 High-Performance Go API Gateway Features:');
    console.log('   • 5x Go instances with concurrent processing');
    console.log('   • Nginx load balancer with optimized settings');
    console.log('   • In-memory caching with Go');
    console.log('   • Rate limiting and connection pooling');
    console.log('   • Optimized for 1000+ concurrent users');
    
    return {
        'high_performance_test': {
            total_requests: totalRequests,
            request_rate: requestRate,
            avg_response_time: avgResponseTime,
            p95_response_time: p95ResponseTime,
            error_rate: errorRate,
            performance_rating: errorRate < 0.05 && p95ResponseTime < 200 ? 'EXCELLENT' : 'GOOD'
        }
    };
}
