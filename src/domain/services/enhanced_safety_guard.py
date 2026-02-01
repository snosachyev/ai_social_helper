"""Enhanced Safety Guard Service with Fallback Strategies"""

from typing import List, Dict, Any, Optional, Union
import logging
import asyncio
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json

from .llama_guard_service import LlamaGuardService, LlamaGuardConfig, SafetyAnalysis, RiskLevel
from .hallucination_detector import HallucinationDetector, HallucinationDetectionConfig, HallucinationResult
from ..entities.query import QueryRequest, GenerationRequest
from ..entities.document import Document, TextChunk


logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategies for safety failures"""
    REJECT = "reject"
    SAFE_RESPONSE = "safe_response"
    LIMITED_RESPONSE = "limited_response"
    HUMAN_REVIEW = "human_review"
    ALTERNATIVE_MODEL = "alternative_model"
    CACHE_ONLY = "cache_only"


class SafetyTier(Enum):
    """Safety tiers for different response levels"""
    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"


@dataclass
class FallbackConfig:
    """Configuration for fallback strategies"""
    default_strategy: FallbackStrategy = FallbackStrategy.REJECT
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_minutes: int = 5
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_degradation: bool = True
    safety_tier: SafetyTier = SafetyTier.MODERATE
    human_review_threshold: float = 0.8
    cache_fallback_ttl_hours: int = 24


@dataclass
class SafetyDecision:
    """Comprehensive safety decision with fallback options"""
    allowed: bool
    primary_reason: str
    risk_level: RiskLevel
    confidence: float
    fallback_strategy: FallbackStrategy
    fallback_responses: List[str]
    requires_human_review: bool
    audit_data: Dict[str, Any]
    metadata: Dict[str, Any]


class CircuitBreaker:
    """Circuit breaker for safety service failures"""
    
    def __init__(self, failure_threshold: int, timeout_minutes: int):
        self.failure_threshold = failure_threshold
        self.timeout_minutes = timeout_minutes
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call_allowed(self) -> bool:
        """Check if service calls are allowed"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if datetime.now() - self.last_failure_time > timedelta(minutes=self.timeout_minutes):
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record a successful call"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class EnhancedSafetyGuard:
    """Enhanced safety guard with comprehensive fallback strategies"""
    
    def __init__(
        self, 
        llama_guard_config: LlamaGuardConfig = None,
        hallucination_config: HallucinationDetectionConfig = None,
        fallback_config: FallbackConfig = None
    ):
        self.llama_guard_config = llama_guard_config or LlamaGuardConfig()
        self.hallucination_config = hallucination_config or HallucinationDetectionConfig()
        self.fallback_config = fallback_config or FallbackConfig()
        
        self.llama_guard = None
        self.hallucination_detector = None
        self.circuit_breaker = CircuitBreaker(
            self.fallback_config.circuit_breaker_threshold,
            self.fallback_config.circuit_breaker_timeout_minutes
        )
        
        self._initialize_services()
        self._setup_fallback_responses()
    
    def _initialize_services(self):
        """Initialize safety services"""
        try:
            self.llama_guard = LlamaGuardService(self.llama_guard_config)
            logger.info("Llama Guard service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Llama Guard: {e}")
            if not self.llama_guard_config.fallback_on_failure:
                raise
        
        try:
            self.hallucination_detector = HallucinationDetector(self.hallucination_config)
            logger.info("Hallucination detector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize hallucination detector: {e}")
            # Hallucination detector is optional
    
    def _setup_fallback_responses(self):
        """Setup predefined fallback responses"""
        self.fallback_responses = {
            FallbackStrategy.REJECT: [
                "I'm unable to process this request due to safety concerns.",
                "This request cannot be fulfilled safely.",
                "For safety reasons, I cannot provide a response to this query."
            ],
            FallbackStrategy.SAFE_RESPONSE: [
                "I can help with general information on this topic. Could you please rephrase your question?",
                "I'd be happy to assist with a safer version of your question.",
                "Let me provide some general information that might be helpful."
            ],
            FallbackStrategy.LIMITED_RESPONSE: [
                "I can provide limited information on this topic.",
                "Here's some basic information that should be safe to share.",
                "I can offer a general overview without going into specific details."
            ],
            FallbackStrategy.HUMAN_REVIEW: [
                "Your request requires human review. Please contact support for assistance.",
                "This query needs additional review. Our team will get back to you soon.",
                "For quality and safety purposes, this request requires manual review."
            ]
        }
    
    async def validate_query(self, query_request: QueryRequest) -> SafetyDecision:
        """Validate query with comprehensive safety checks and fallbacks"""
        audit_data = {
            "query_id": str(query_request.query_id),
            "timestamp": datetime.now().isoformat(),
            "validation_type": "query"
        }
        
        try:
            # Check circuit breaker
            if not self.circuit_breaker.call_allowed():
                return self._create_circuit_breaker_fallback(audit_data)
            
            # Perform safety analysis with retries
            safety_analysis = await self._perform_safety_analysis_with_retries(
                query_request.query, "input"
            )
            
            if not safety_analysis:
                return self._create_analysis_failure_fallback(audit_data)
            
            # Make decision based on safety tier
            decision = self._make_safety_decision(
                safety_analysis, audit_data, is_query=True
            )
            
            self.circuit_breaker.record_success()
            return decision
            
        except Exception as e:
            logger.error(f"Query validation failed: {e}")
            self.circuit_breaker.record_failure()
            return self._create_error_fallback(str(e), audit_data)
    
    async def validate_generation(
        self, 
        generation_request: GenerationRequest, 
        generated_response: str = None
    ) -> SafetyDecision:
        """Validate generation request and response"""
        audit_data = {
            "request_id": str(generation_request.request_id),
            "timestamp": datetime.now().isoformat(),
            "validation_type": "generation"
        }
        
        try:
            # Check circuit breaker
            if not self.circuit_breaker.call_allowed():
                return self._create_circuit_breaker_fallback(audit_data)
            
            # Validate input first
            input_analysis = await self._perform_safety_analysis_with_retries(
                generation_request.query, "input"
            )
            
            if not input_analysis or not input_analysis.is_safe:
                decision = self._make_safety_decision(
                    input_analysis, audit_data, is_query=True
                )
                self.circuit_breaker.record_success()
                return decision
            
            # If response is provided, validate it too
            if generated_response:
                output_analysis = await self._perform_safety_analysis_with_retries(
                    generated_response, "output"
                )
                
                # Check for hallucinations
                hallucination_result = None
                if self.hallucination_detector and generation_request.context:
                    hallucination_result = await self.hallucination_detector.detect_hallucination(
                        generation_request.query,
                        generated_response,
                        generation_request.context
                    )
                
                # Combine analyses
                combined_analysis = self._combine_analyses(
                    output_analysis, hallucination_result
                )
                
                decision = self._make_safety_decision(
                    combined_analysis, audit_data, is_query=False
                )
            else:
                # Only input validation
                decision = SafetyDecision(
                    allowed=True,
                    primary_reason="Input validation passed",
                    risk_level=RiskLevel.LOW,
                    confidence=0.8,
                    fallback_strategy=FallbackStrategy.REJECT,
                    fallback_responses=[],
                    requires_human_review=False,
                    audit_data=audit_data,
                    metadata={"validation_type": "input_only"}
                )
            
            self.circuit_breaker.record_success()
            return decision
            
        except Exception as e:
            logger.error(f"Generation validation failed: {e}")
            self.circuit_breaker.record_failure()
            return self._create_error_fallback(str(e), audit_data)
    
    async def _perform_safety_analysis_with_retries(
        self, 
        text: str, 
        content_type: str
    ) -> Optional[SafetyAnalysis]:
        """Perform safety analysis with retry logic"""
        for attempt in range(self.fallback_config.max_retry_attempts):
            try:
                if self.llama_guard:
                    if content_type == "input":
                        return await self.llama_guard.analyze_input(
                            QueryRequest(query=text, query_id="", metadata={})
                        )
                    else:
                        return await self.llama_guard.analyze_output(text)
                else:
                    # Use fallback analysis
                    return await self._perform_fallback_analysis(text)
                    
            except Exception as e:
                logger.warning(f"Safety analysis attempt {attempt + 1} failed: {e}")
                if attempt < self.fallback_config.max_retry_attempts - 1:
                    await asyncio.sleep(self.fallback_config.retry_delay_seconds)
                else:
                    logger.error(f"All safety analysis attempts failed for: {text[:100]}...")
                    return None
        
        return None
    
    async def _perform_fallback_analysis(self, text: str) -> SafetyAnalysis:
        """Perform basic fallback safety analysis"""
        # Simple keyword-based safety check
        unsafe_keywords = [
            "violence", "hate", "kill", "harm", "illegal", 
            "password", "secret", "private_key"
        ]
        
        text_lower = text.lower()
        risk_score = 0.0
        flagged_content = []
        
        for keyword in unsafe_keywords:
            if keyword in text_lower:
                risk_score += 0.2
                flagged_content.append(keyword)
        
        is_safe = risk_score < 0.5
        
        return SafetyAnalysis(
            is_safe=is_safe,
            risk_scores={},  # Simplified
            overall_risk=risk_score,
            risk_level=RiskLevel.LOW if risk_score < 0.3 else RiskLevel.MEDIUM,
            reasoning=f"Fallback analysis: {'Safe' if is_safe else 'Unsafe'}",
            flagged_content=flagged_content,
            suggestions=["Review content"] if not is_safe else [],
            metadata={"analysis_type": "fallback"}
        )
    
    def _make_safety_decision(
        self, 
        analysis: SafetyAnalysis, 
        audit_data: Dict[str, Any],
        is_query: bool
    ) -> SafetyDecision:
        """Make safety decision based on analysis and configuration"""
        allowed = analysis.is_safe
        risk_level = analysis.risk_level
        confidence = 1.0 - analysis.overall_risk
        
        # Apply safety tier logic
        if self.fallback_config.safety_tier == SafetyTier.STRICT:
            allowed = allowed and analysis.overall_risk < 0.2
        elif self.fallback_config.safety_tier == SafetyTier.PERMISSIVE:
            allowed = allowed and analysis.overall_risk < 0.8
        
        # Determine fallback strategy
        if not allowed:
            if analysis.overall_risk >= self.fallback_config.human_review_threshold:
                fallback_strategy = FallbackStrategy.HUMAN_REVIEW
            else:
                fallback_strategy = self.fallback_config.default_strategy
        else:
            fallback_strategy = FallbackStrategy.REJECT
        
        # Check if human review is needed
        requires_human_review = (
            analysis.overall_risk >= self.fallback_config.human_review_threshold or
            risk_level == RiskLevel.CRITICAL
        )
        
        # Get fallback responses
        fallback_responses = self.fallback_responses.get(fallback_strategy, [])
        
        # Update audit data
        audit_data.update({
            "analysis_result": analysis.is_safe,
            "risk_score": analysis.overall_risk,
            "risk_level": risk_level.value,
            "flagged_content": analysis.flagged_content,
            "fallback_strategy": fallback_strategy.value
        })
        
        return SafetyDecision(
            allowed=allowed,
            primary_reason=analysis.reasoning,
            risk_level=risk_level,
            confidence=confidence,
            fallback_strategy=fallback_strategy,
            fallback_responses=fallback_responses,
            requires_human_review=requires_human_review,
            audit_data=audit_data,
            metadata={
                "safety_tier": self.fallback_config.safety_tier.value,
                "analysis_metadata": analysis.metadata
            }
        )
    
    def _combine_analyses(
        self, 
        safety_analysis: SafetyAnalysis, 
        hallucination_result: Optional[HallucinationResult]
    ) -> SafetyAnalysis:
        """Combine safety and hallucination analyses"""
        if not hallucination_result:
            return safety_analysis
        
        # Adjust risk based on hallucination detection
        combined_risk = max(safety_analysis.overall_risk, hallucination_result.confidence_score)
        
        # Combine flagged content
        combined_flagged = safety_analysis.flagged_content.copy()
        if hallucination_result.is_hallucinated:
            combined_flagged.extend([f"hallucination: {ht.value}" for ht in hallucination_result.hallucination_types])
        
        # Combine reasoning
        combined_reasoning = safety_analysis.reasoning
        if hallucination_result.is_hallucinated:
            combined_reasoning += f"; Hallucination detected: {', '.join(hallucination_result.explanations)}"
        
        return SafetyAnalysis(
            is_safe=safety_analysis.is_safe and not hallucination_result.is_hallucinated,
            risk_scores=safety_analysis.risk_scores,
            overall_risk=combined_risk,
            risk_level=self._calculate_risk_level(combined_risk),
            reasoning=combined_reasoning,
            flagged_content=combined_flagged,
            suggestions=safety_analysis.suggestions + hallucination_result.suggestions,
            metadata={
                **safety_analysis.metadata,
                "hallucination_detection": hallucination_result.metadata
            }
        )
    
    def _calculate_risk_level(self, risk_score: float) -> RiskLevel:
        """Calculate risk level from score"""
        if risk_score >= 0.8:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            return RiskLevel.HIGH
        elif risk_score >= 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _create_circuit_breaker_fallback(self, audit_data: Dict[str, Any]) -> SafetyDecision:
        """Create fallback response when circuit breaker is open"""
        audit_data.update({
            "fallback_reason": "circuit_breaker_open",
            "failure_count": self.circuit_breaker.failure_count
        })
        
        return SafetyDecision(
            allowed=False,
            primary_reason="Safety service temporarily unavailable",
            risk_level=RiskLevel.HIGH,
            confidence=0.0,
            fallback_strategy=FallbackStrategy.REJECT,
            fallback_responses=self.fallback_responses[FallbackStrategy.REJECT],
            requires_human_review=False,
            audit_data=audit_data,
            metadata={"circuit_breaker_state": self.circuit_breaker.state}
        )
    
    def _create_analysis_failure_fallback(self, audit_data: Dict[str, Any]) -> SafetyDecision:
        """Create fallback response when analysis fails"""
        audit_data.update({
            "fallback_reason": "analysis_failure"
        })
        
        return SafetyDecision(
            allowed=False,
            primary_reason="Safety analysis failed",
            risk_level=RiskLevel.HIGH,
            confidence=0.0,
            fallback_strategy=FallbackStrategy.REJECT,
            fallback_responses=self.fallback_responses[FallbackStrategy.REJECT],
            requires_human_review=True,
            audit_data=audit_data,
            metadata={"error_type": "analysis_failure"}
        )
    
    def _create_error_fallback(self, error_message: str, audit_data: Dict[str, Any]) -> SafetyDecision:
        """Create fallback response for general errors"""
        audit_data.update({
            "fallback_reason": "general_error",
            "error_message": error_message
        })
        
        return SafetyDecision(
            allowed=False,
            primary_reason=f"Safety validation error: {error_message}",
            risk_level=RiskLevel.CRITICAL,
            confidence=0.0,
            fallback_strategy=FallbackStrategy.REJECT,
            fallback_responses=self.fallback_responses[FallbackStrategy.REJECT],
            requires_human_review=True,
            audit_data=audit_data,
            metadata={"error_type": "general_error"}
        )
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "state": self.circuit_breaker.state,
            "failure_count": self.circuit_breaker.failure_count,
            "failure_threshold": self.circuit_breaker.failure_threshold,
            "last_failure_time": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None,
            "timeout_minutes": self.circuit_breaker.timeout_minutes
        }
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker to closed state"""
        self.circuit_breaker.state = "CLOSED"
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.last_failure_time = None
        logger.info("Circuit breaker reset to CLOSED state")
