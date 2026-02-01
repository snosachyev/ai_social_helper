"""Production-ready Rate Limiting Middleware"""

import time
import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    # Default limits
    default_requests_per_minute: int = 60
    default_requests_per_hour: int = 1000
    default_requests_per_day: int = 10000
    
    # Burst limits
    burst_requests: int = 10
    burst_window_seconds: int = 10
    
    # Redis settings
    redis_key_prefix: str = "rate_limit"
    cleanup_interval: int = 300  # 5 minutes
    
    # Special limits for different endpoints
    endpoint_limits: Dict[str, Dict[str, int]] = None
    
    def __post_init__(self):
        if self.endpoint_limits is None:
            self.endpoint_limits = {
                "/generate": {"requests_per_minute": 20, "requests_per_hour": 200},
                "/query": {"requests_per_minute": 30, "requests_per_hour": 300},
                "/documents/upload": {"requests_per_minute": 10, "requests_per_hour": 50},
                "/auth/login": {"requests_per_minute": 5, "requests_per_hour": 20}
            }


class RedisRateLimiter:
    """Redis-based distributed rate limiter."""
    
    def __init__(self, redis_client: redis.Redis, config: RateLimitConfig):
        self.redis = redis_client
        self.config = config
        self.local_cache: Dict[str, Tuple[int, float]] = {}  # Fallback local cache
    
    async def is_allowed(
        self,
        key: str,
        endpoint: str = None,
        user_id: str = None
    ) -> Tuple[bool, Dict[str, int]]:
        """Check if request is allowed and return rate limit info."""
        try:
            # Get limits for endpoint
            limits = self._get_limits(endpoint)
            
            # Create Redis keys
            now = int(time.time())
            minute_key = f"{self.config.redis_key_prefix}:minute:{key}"
            hour_key = f"{self.config.redis_key_prefix}:hour:{key}"
            day_key = f"{self.config.redis_key_prefix}:day:{key}"
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Check minute limit
            pipe.zremrangebyscore(minute_key, 0, now - 60)
            pipe.zcard(minute_key)
            minute_count = await pipe.execute()[-1]
            
            # Check hour limit  
            pipe.zremrangebyscore(hour_key, 0, now - 3600)
            pipe.zcard(hour_key)
            hour_count = await pipe.execute()[-1]
            
            # Check day limit
            pipe.zremrangebyscore(day_key, 0, now - 86400)
            pipe.zcard(day_key)
            day_count = await pipe.execute()[-1]
            
            # Check if any limit exceeded
            if minute_count >= limits["requests_per_minute"]:
                return False, {
                    "minute": minute_count,
                    "hour": hour_count,
                    "day": day_count,
                    "limit_type": "minute",
                    "limit": limits["requests_per_minute"]
                }
            
            if hour_count >= limits["requests_per_hour"]:
                return False, {
                    "minute": minute_count,
                    "hour": hour_count,
                    "day": day_count,
                    "limit_type": "hour",
                    "limit": limits["requests_per_hour"]
                }
            
            if day_count >= limits["requests_per_day"]:
                return False, {
                    "minute": minute_count,
                    "hour": hour_count,
                    "day": day_count,
                    "limit_type": "day",
                    "limit": limits["requests_per_day"]
                }
            
            # Add current request to all time windows
            pipe = self.redis.pipeline()
            pipe.zadd(minute_key, {str(now): now})
            pipe.zadd(hour_key, {str(now): now})
            pipe.zadd(day_key, {str(now): now})
            pipe.expire(minute_key, 300)  # 5 minutes TTL
            pipe.expire(hour_key, 7200)   # 2 hours TTL
            pipe.expire(day_key, 172800)  # 2 days TTL
            await pipe.execute()
            
            return True, {
                "minute": minute_count + 1,
                "hour": hour_count + 1,
                "day": day_count + 1
            }
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fallback to local cache if Redis fails
            return self._local_fallback(key, endpoint)
    
    def _get_limits(self, endpoint: str) -> Dict[str, int]:
        """Get rate limits for endpoint."""
        if endpoint and endpoint in self.config.endpoint_limits:
            limits = self.config.endpoint_limits[endpoint]
            return {
                "requests_per_minute": limits.get("requests_per_minute", self.config.default_requests_per_minute),
                "requests_per_hour": limits.get("requests_per_hour", self.config.default_requests_per_hour),
                "requests_per_day": self.config.default_requests_per_day
            }
        
        return {
            "requests_per_minute": self.config.default_requests_per_minute,
            "requests_per_hour": self.config.default_requests_per_hour,
            "requests_per_day": self.config.default_requests_per_day
        }
    
    def _local_fallback(self, key: str, endpoint: str) -> Tuple[bool, Dict[str, int]]:
        """Local cache fallback when Redis is unavailable."""
        now = time.time()
        
        if key in self.local_cache:
            count, last_reset = self.local_cache[key]
            
            # Reset if window expired
            if now - last_reset > 60:  # 1 minute window
                count = 0
                last_reset = now
            
            limits = self._get_limits(endpoint)
            
            if count >= limits["requests_per_minute"]:
                return False, {
                    "minute": count,
                    "hour": count,
                    "day": count,
                    "limit_type": "minute",
                    "limit": limits["requests_per_minute"]
                }
            
            self.local_cache[key] = (count + 1, last_reset)
            return True, {"minute": count + 1, "hour": count + 1, "day": count + 1}
        
        # First request
        self.local_cache[key] = (1, now)
        return True, {"minute": 1, "hour": 1, "day": 1}
    
    async def get_rate_limit_info(self, key: str, endpoint: str = None) -> Dict[str, int]:
        """Get current rate limit usage."""
        try:
            limits = self._get_limits(endpoint)
            now = int(time.time())
            
            minute_key = f"{self.config.redis_key_prefix}:minute:{key}"
            hour_key = f"{self.config.redis_key_prefix}:hour:{key}"
            day_key = f"{self.config.redis_key_prefix}:day:{key}"
            
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(minute_key, 0, now - 60)
            pipe.zcard(minute_key)
            pipe.zremrangebyscore(hour_key, 0, now - 3600)
            pipe.zcard(hour_key)
            pipe.zremrangebyscore(day_key, 0, now - 86400)
            pipe.zcard(day_key)
            
            results = await pipe.execute()
            
            return {
                "minute": results[1],
                "hour": results[3],
                "day": results[5],
                "limits": limits
            }
            
        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}")
            return {"minute": 0, "hour": 0, "day": 0, "limits": self._get_limits(endpoint)}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI."""
    
    def __init__(self, app, redis_client: redis.Redis, config: RateLimitConfig = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.rate_limiter = RedisRateLimiter(redis_client, self.config)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        is_allowed, limit_info = await self.rate_limiter.is_allowed(
            key=client_id,
            endpoint=request.url.path,
            user_id=request.headers.get("X-User-ID")
        )
        
        if not is_allowed:
            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(limit_info["limit"]),
                "X-RateLimit-Remaining": str(max(0, limit_info["limit"] - limit_info[limit_info["limit_type"]])),
                "X-RateLimit-Reset": str(int(time.time()) + 60),  # Reset in 1 minute
                "Retry-After": "60"
            }
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit_type": limit_info["limit_type"],
                    "limit": limit_info["limit"],
                    "current": limit_info[limit_info["limit_type"]]
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        limits = limit_info.get("limits", {})
        response.headers["X-RateLimit-Limit-Minute"] = str(limits.get("requests_per_minute", self.config.default_requests_per_minute))
        response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, limits.get("requests_per_minute", self.config.default_requests_per_minute) - limit_info["minute"]))
        response.headers["X-RateLimit-Limit-Hour"] = str(limits.get("requests_per_hour", self.config.default_requests_per_hour))
        response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, limits.get("requests_per_hour", self.config.default_requests_per_hour) - limit_info["hour"]))
        response.headers["X-RateLimit-Limit-Day"] = str(limits.get("requests_per_day", self.config.default_requests_per_day))
        response.headers["X-RateLimit-Remaining-Day"] = str(max(0, limits.get("requests_per_day", self.config.default_requests_per_day) - limit_info["day"]))
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Priority order: User ID > API Key > IP Address
        
        # Check for user ID in header
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"
        
        # Fall back to IP address
        client_ip = request.client.host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for more accurate limiting."""
    
    def __init__(self, redis_client: redis.Redis, window_size: int = 60, max_requests: int = 100):
        self.redis = redis_client
        self.window_size = window_size
        self.max_requests = max_requests
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed using sliding window."""
        try:
            now = time.time()
            window_start = now - self.window_size
            
            # Remove old entries
            await self.redis.zremrangebyscore(f"sliding:{key}", 0, window_start)
            
            # Count current requests
            current_count = await self.redis.zcard(f"sliding:{key}")
            
            if current_count >= self.max_requests:
                return False
            
            # Add current request
            await self.redis.zadd(f"sliding:{key}", {str(now): now})
            await self.redis.expire(f"sliding:{key}", self.window_size + 10)
            
            return True
            
        except Exception as e:
            logger.error(f"Sliding window rate limiter error: {e}")
            return True  # Fail open


class TokenBucketRateLimiter:
    """Token bucket rate limiter for burst handling."""
    
    def __init__(self, redis_client: redis.Redis, capacity: int = 10, refill_rate: float = 1.0):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
    
    async def consume(self, key: str, tokens: int = 1) -> bool:
        """Consume tokens from bucket."""
        try:
            now = time.time()
            
            # Get current bucket state
            bucket_data = await self.redis.hgetall(f"bucket:{key}")
            
            if not bucket_data:
                # Initialize new bucket
                bucket_data = {
                    "tokens": str(self.capacity),
                    "last_refill": str(now)
                }
            else:
                # Refill tokens based on time elapsed
                last_refill = float(bucket_data["last_refill"])
                time_elapsed = now - last_refill
                tokens_to_add = time_elapsed * self.refill_rate
                
                current_tokens = min(
                    self.capacity,
                    float(bucket_data["tokens"]) + tokens_to_add
                )
                
                bucket_data["tokens"] = str(current_tokens)
                bucket_data["last_refill"] = str(now)
            
            # Check if enough tokens
            current_tokens = float(bucket_data["tokens"])
            if current_tokens < tokens:
                return False
            
            # Consume tokens
            bucket_data["tokens"] = str(current_tokens - tokens)
            
            # Update Redis
            await self.redis.hset(f"bucket:{key}", mapping=bucket_data)
            await self.redis.expire(f"bucket:{key}", 3600)  # 1 hour TTL
            
            return True
            
        except Exception as e:
            logger.error(f"Token bucket rate limiter error: {e}")
            return True  # Fail open
