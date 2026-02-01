"""Production-ready Circuit Breaker Middleware"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import httpx
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    # Failure thresholds
    failure_threshold: int = 5          # Number of failures before opening
    success_threshold: int = 3          # Number of successes to close circuit
    
    # Time thresholds
    timeout_seconds: int = 60           # How long to wait before trying again
    recovery_timeout: int = 30           # How long to stay in half-open state
    
    # Monitoring
    monitor_window: int = 300           # Time window for monitoring (seconds)
    min_requests: int = 10              # Minimum requests before calculating failure rate
    
    # Advanced settings
    failure_rate_threshold: float = 0.5  # Failure rate threshold (0.0-1.0)
    expected_exception: type = Exception  # Expected exception type
    
    # Service-specific configs
    service_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    requests: int = 0
    failures: int = 0
    successes: int = 0
    timeouts: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: datetime = field(default_factory=datetime.utcnow)


class CircuitBreaker:
    """Individual circuit breaker for a service."""
    
    def __init__(self, service_name: str, config: CircuitBreakerConfig):
        self.service_name = service_name
        self.config = config
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        
        # Get service-specific config if available
        service_config = config.service_configs.get(service_name, {})
        self.failure_threshold = service_config.get("failure_threshold", config.failure_threshold)
        self.timeout_seconds = service_config.get("timeout_seconds", config.timeout_seconds)
        self.success_threshold = service_config.get("success_threshold", config.success_threshold)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.stats.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.state_changed_at = datetime.utcnow()
                    logger.info(f"Circuit breaker for {self.service_name} entering HALF_OPEN state")
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service {self.service_name} is temporarily unavailable (circuit open)"
                    )
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self._record_success()
            return result
            
        except self.config.expected_exception as e:
            # Record failure
            await self._record_failure()
            raise
        
        except Exception as e:
            # Record failure for unexpected exceptions too
            await self._record_failure()
            raise
    
    async def _record_success(self):
        """Record a successful request."""
        async with self._lock:
            self.stats.requests += 1
            self.stats.successes += 1
            self.stats.last_success_time = datetime.utcnow()
            
            if self.stats.state == CircuitState.HALF_OPEN:
                if self.stats.successes >= self.success_threshold:
                    self.stats.state = CircuitState.CLOSED
                    self.stats.state_changed_at = datetime.utcnow()
                    self.stats.successes = 0  # Reset counter
                    logger.info(f"Circuit breaker for {self.service_name} closed")
    
    async def _record_failure(self):
        """Record a failed request."""
        async with self._lock:
            self.stats.requests += 1
            self.stats.failures += 1
            self.stats.last_failure_time = datetime.utcnow()
            
            if self.stats.state == CircuitState.CLOSED:
                if self._should_open_circuit():
                    self.stats.state = CircuitState.OPEN
                    self.stats.state_changed_at = datetime.utcnow()
                    logger.warning(f"Circuit breaker for {self.service_name} opened")
            
            elif self.stats.state == CircuitState.HALF_OPEN:
                self.stats.state = CircuitState.OPEN
                self.stats.state_changed_at = datetime.utcnow()
                logger.warning(f"Circuit breaker for {self.service_name} re-opened from HALF_OPEN")
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened."""
        # Check failure count
        if self.stats.failures >= self.failure_threshold:
            return True
        
        # Check failure rate
        if self.stats.requests >= self.config.min_requests:
            failure_rate = self.stats.failures / self.stats.requests
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if self.stats.state != CircuitState.OPEN:
            return False
        
        if not self.stats.last_failure_time:
            return True
        
        time_since_failure = datetime.utcnow() - self.stats.last_failure_time
        return time_since_failure.total_seconds() >= self.timeout_seconds
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "service_name": self.service_name,
            "state": self.stats.state.value,
            "requests": self.stats.requests,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "failure_rate": self.stats.failures / max(self.stats.requests, 1),
            "last_failure_time": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            "last_success_time": self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
            "state_changed_at": self.stats.state_changed_at.isoformat(),
            "config": {
                "failure_threshold": self.failure_threshold,
                "timeout_seconds": self.timeout_seconds,
                "success_threshold": self.success_threshold
            }
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(service_name, self.config)
        return self.circuit_breakers[service_name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {
            name: cb.get_stats()
            for name, cb in self.circuit_breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            async with cb._lock:
                cb.stats = CircuitBreakerStats()
                logger.info(f"Reset circuit breaker for {cb.service_name}")


class ResilientHTTPClient:
    """HTTP client with circuit breaker protection."""
    
    def __init__(self, circuit_breaker_registry: CircuitBreakerRegistry):
        self.registry = circuit_breaker_registry
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make GET request with circuit breaker protection."""
        circuit_breaker = self.registry.get_circuit_breaker(service_name)
        return await circuit_breaker.call(self.client.get, url, **kwargs)
    
    async def post(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make POST request with circuit breaker protection."""
        circuit_breaker = self.registry.get_circuit_breaker(service_name)
        return await circuit_breaker.call(self.client.post, url, **kwargs)
    
    async def put(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make PUT request with circuit breaker protection."""
        circuit_breaker = self.registry.get_circuit_breaker(service_name)
        return await circuit_breaker.call(self.client.put, url, **kwargs)
    
    async def delete(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request with circuit breaker protection."""
        circuit_breaker = self.registry.get_circuit_breaker(service_name)
        return await circuit_breaker.call(self.client.delete, url, **kwargs)
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """Circuit breaker middleware for FastAPI."""
    
    def __init__(self, app, config: CircuitBreakerConfig = None):
        super().__init__(app)
        self.config = config or CircuitBreakerConfig()
        self.registry = CircuitBreakerRegistry(self.config)
        self.http_client = ResilientHTTPClient(self.registry)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with circuit breaker monitoring."""
        # Skip circuit breaker for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Add circuit breaker info to request state
        request.state.circuit_breaker_registry = self.registry
        request.state.http_client = self.http_client
        
        try:
            response = await call_next(request)
            
            # Add circuit breaker headers
            stats = self.registry.get_all_stats()
            response.headers["X-Circuit-Breaker-Status"] = json.dumps(stats)
            
            return response
            
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.http_client.close()


class RetryPolicy:
    """Retry policy for failed requests."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry policy."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    break
                
                # Calculate delay
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )
                
                if self.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)
                
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
        raise last_exception


class Bulkhead:
    """Bulkhead pattern for limiting concurrent requests."""
    
    def __init__(self, max_concurrent: int, max_queue: int = 100):
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue = asyncio.Queue(maxsize=max_queue)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with bulkhead protection."""
        # Check if queue is full
        if self.queue.full():
            raise HTTPException(
                status_code=503,
                detail="Service is temporarily overloaded (bulkhead queue full)"
            )
        
        # Add to queue
        await self.queue.put(None)
        
        try:
            async with self.semaphore:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        finally:
            # Remove from queue
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
