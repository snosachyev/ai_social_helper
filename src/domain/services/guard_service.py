"""Guard domain service - Input validation and security"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Protocol, runtime_checkable
import re
import logging
from dataclasses import dataclass

from ..entities.query import QueryRequest, GenerationRequest
from ..entities.document import Document, TextChunk


logger = logging.getLogger(__name__)


@runtime_checkable
class Guard(Protocol):
    """Protocol for security guards"""
    
    async def validate_query(self, query_request: QueryRequest) -> "GuardResult":
        """Validate query request"""
        ...
    
    async def validate_generation(self, generation_request: GenerationRequest) -> "GuardResult":
        """Validate generation request"""
        ...


@dataclass
class GuardConfig:
    """Configuration for guard service"""
    max_query_length: int = 1000
    max_context_length: int = 10000
    blocked_words: List[str] = None
    allowed_patterns: List[str] = None
    enable_content_filter: bool = True
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 60
    
    def __post_init__(self):
        if self.blocked_words is None:
            self.blocked_words = [
                "password", "secret", "token", "api_key", "private_key",
                "credit_card", "ssn", "social_security", "confidential"
            ]
        if self.allowed_patterns is None:
            self.allowed_patterns = [
                r"^[a-zA-Z0-9\s\.,!?;:'\"-]+$"  # Basic ASCII characters
            ]


@dataclass
class GuardResult:
    """Result of guard validation"""
    is_allowed: bool
    reason: str = ""
    risk_score: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SecurityGuard:
    """Security guard implementation"""
    
    def __init__(self, config: GuardConfig = None):
        self.config = config or GuardConfig()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self.blocked_patterns = [
            re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            for word in self.config.blocked_words
        ]
        self.allowed_patterns = [
            re.compile(pattern)
            for pattern in self.config.allowed_patterns
        ]
    
    async def validate_query(self, query_request: QueryRequest) -> GuardResult:
        """Validate query request"""
        try:
            # Length validation
            if len(query_request.query) > self.config.max_query_length:
                return GuardResult(
                    is_allowed=False,
                    reason=f"Query too long: {len(query_request.query)} > {self.config.max_query_length}",
                    risk_score=0.8
                )
            
            # Content validation
            content_result = self._validate_content(query_request.query)
            if not content_result.is_allowed:
                return content_result
            
            # Pattern validation
            pattern_result = self._validate_patterns(query_request.query)
            if not pattern_result.is_allowed:
                return pattern_result
            
            # Additional metadata validation
            metadata_result = self._validate_metadata(query_request.metadata)
            if not metadata_result.is_allowed:
                return metadata_result
            
            return GuardResult(
                is_allowed=True,
                reason="Query validation passed",
                risk_score=0.1
            )
            
        except Exception as e:
            logger.error(f"Query validation error: {e}")
            return GuardResult(
                is_allowed=False,
                reason=f"Validation error: {str(e)}",
                risk_score=0.9
            )
    
    async def validate_generation(self, generation_request: GenerationRequest) -> GuardResult:
        """Validate generation request"""
        try:
            # Query validation
            query_result = await self.validate_query(
                QueryRequest(
                    query=generation_request.query,
                    metadata=generation_request.metadata
                )
            )
            if not query_result.is_allowed:
                return GuardResult(
                    is_allowed=False,
                    reason=f"Query validation failed: {query_result.reason}",
                    risk_score=query_result.risk_score
                )
            
            # Context validation
            context_text = generation_request.get_context_text()
            if len(context_text) > self.config.max_context_length:
                return GuardResult(
                    is_allowed=False,
                    reason=f"Context too long: {len(context_text)} > {self.config.max_context_length}",
                    risk_score=0.7
                )
            
            # Context content validation
            context_result = self._validate_content(context_text)
            if not context_result.is_allowed:
                return GuardResult(
                    is_allowed=False,
                    reason=f"Context validation failed: {context_result.reason}",
                    risk_score=context_result.risk_score
                )
            
            # Parameter validation
            if generation_request.max_tokens > 2048:
                return GuardResult(
                    is_allowed=False,
                    reason=f"max_tokens too high: {generation_request.max_tokens}",
                    risk_score=0.6
                )
            
            if generation_request.temperature > 1.5:
                return GuardResult(
                    is_allowed=False,
                    reason=f"temperature too high: {generation_request.temperature}",
                    risk_score=0.5
                )
            
            return GuardResult(
                is_allowed=True,
                reason="Generation validation passed",
                risk_score=0.1
            )
            
        except Exception as e:
            logger.error(f"Generation validation error: {e}")
            return GuardResult(
                is_allowed=False,
                reason=f"Validation error: {str(e)}",
                risk_score=0.9
            )
    
    def _validate_content(self, text: str) -> GuardResult:
        """Validate text content against blocked words"""
        if not self.config.enable_content_filter:
            return GuardResult(is_allowed=True)
        
        text_lower = text.lower()
        risk_score = 0.0
        blocked_words_found = []
        
        for pattern in self.blocked_patterns:
            matches = pattern.findall(text_lower)
            if matches:
                blocked_words_found.extend(matches)
                risk_score += 0.2
        
        if blocked_words_found:
            return GuardResult(
                is_allowed=False,
                reason=f"Blocked content detected: {', '.join(set(blocked_words_found))}",
                risk_score=min(risk_score, 1.0),
                metadata={"blocked_words": blocked_words_found}
            )
        
        return GuardResult(is_allowed=True, risk_score=risk_score)
    
    def _validate_patterns(self, text: str) -> GuardResult:
        """Validate text against allowed patterns"""
        if not self.allowed_patterns:
            return GuardResult(is_allowed=True)
        
        for pattern in self.allowed_patterns:
            if pattern.fullmatch(text):
                return GuardResult(is_allowed=True)
        
        return GuardResult(
            is_allowed=False,
            reason="Text contains invalid characters",
            risk_score=0.6
        )
    
    def _validate_metadata(self, metadata: Dict[str, Any]) -> GuardResult:
        """Validate metadata"""
        if not metadata:
            return GuardResult(is_allowed=True)
        
        # Check for suspicious metadata keys
        suspicious_keys = ["password", "secret", "key", "token"]
        for key in metadata.keys():
            if any(sus in key.lower() for sus in suspicious_keys):
                return GuardResult(
                    is_allowed=False,
                    reason=f"Suspicious metadata key: {key}",
                    risk_score=0.8
                )
        
        # Check metadata size
        metadata_str = str(metadata)
        if len(metadata_str) > 1000:
            return GuardResult(
                is_allowed=False,
                reason="Metadata too large",
                risk_score=0.5
            )
        
        return GuardResult(is_allowed=True)


class RateLimitGuard:
    """Rate limiting guard"""
    
    def __init__(self, config: GuardConfig = None):
        self.config = config or GuardConfig()
        self.request_counts: Dict[str, List[float]] = {}
    
    async def validate_query(self, query_request: QueryRequest) -> GuardResult:
        """Validate query with rate limiting"""
        if not self.config.enable_rate_limiting:
            return GuardResult(is_allowed=True)
        
        client_id = query_request.metadata.get("client_id", "anonymous")
        import time
        current_time = time.time()
        
        # Clean old requests
        if client_id in self.request_counts:
            self.request_counts[client_id] = [
                req_time for req_time in self.request_counts[client_id]
                if current_time - req_time < 60  # Keep last minute
            ]
        else:
            self.request_counts[client_id] = []
        
        # Check rate limit
        if len(self.request_counts[client_id]) >= self.config.max_requests_per_minute:
            return GuardResult(
                is_allowed=False,
                reason="Rate limit exceeded",
                risk_score=0.9,
                metadata={"requests_per_minute": len(self.request_counts[client_id])}
            )
        
        # Add current request
        self.request_counts[client_id].append(current_time)
        
        return GuardResult(is_allowed=True)
    
    async def validate_generation(self, generation_request: GenerationRequest) -> GuardResult:
        """Validate generation with rate limiting"""
        # Reuse query validation logic
        return await self.validate_query(
            QueryRequest(
                query=generation_request.query,
                metadata=generation_request.metadata
            )
        )


class CompositeGuard:
    """Composite guard that combines multiple guards"""
    
    def __init__(self, guards: List[Guard]):
        self.guards = guards
    
    async def validate_query(self, query_request: QueryRequest) -> GuardResult:
        """Validate query using all guards"""
        for guard in self.guards:
            result = await guard.validate_query(query_request)
            if not result.is_allowed:
                return result
        
        return GuardResult(
            is_allowed=True,
            reason="All guards passed",
            risk_score=0.1
        )
    
    async def validate_generation(self, generation_request: GenerationRequest) -> GuardResult:
        """Validate generation using all guards"""
        for guard in self.guards:
            result = await guard.validate_generation(generation_request)
            if not result.is_allowed:
                return result
        
        return GuardResult(
            is_allowed=True,
            reason="All guards passed",
            risk_score=0.1
        )
