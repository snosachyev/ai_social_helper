"""Enhanced Llama Guard Integration for RAG System"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio
from dataclasses import dataclass
from enum import Enum
import json
import re
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from datetime import datetime, timedelta

from ..entities.query import QueryRequest, GenerationRequest
from ..entities.document import Document, TextChunk


logger = logging.getLogger(__name__)


class SafetyCategory(Enum):
    """Safety categories for content classification"""
    VIOLENCE = "violence"
    HATE = "hate"
    SEXUAL = "sexual"
    SELF_HARM = "self_harm"
    ILLEGAL = "illegal"
    PRIVACY = "privacy"
    MISINFORMATION = "misinformation"
    TOXICITY = "toxicity"


class RiskLevel(Enum):
    """Risk levels for safety decisions"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class LlamaGuardConfig:
    """Configuration for Llama Guard integration"""
    model_name: str = "meta-llama/LlamaGuard-7b"
    device: str = "auto"
    torch_dtype: str = "float16"
    max_length: int = 512
    batch_size: int = 4
    enable_input_filtering: bool = True
    enable_output_filtering: bool = True
    enable_context_analysis: bool = True
    risk_thresholds: Dict[SafetyCategory, float] = None
    fallback_on_failure: bool = True
    cache_results: bool = True
    cache_ttl_minutes: int = 60
    
    def __post_init__(self):
        if self.risk_thresholds is None:
            self.risk_thresholds = {
                SafetyCategory.VIOLENCE: 0.7,
                SafetyCategory.HATE: 0.6,
                SafetyCategory.SEXUAL: 0.8,
                SafetyCategory.SELF_HARM: 0.9,
                SafetyCategory.ILLEGAL: 0.8,
                SafetyCategory.PRIVACY: 0.7,
                SafetyCategory.MISINFORMATION: 0.6,
                SafetyCategory.TOXICITY: 0.5
            }


@dataclass
class SafetyAnalysis:
    """Result of safety analysis"""
    is_safe: bool
    risk_scores: Dict[SafetyCategory, float]
    overall_risk: float
    risk_level: RiskLevel
    reasoning: str
    flagged_content: List[str]
    suggestions: List[str]
    metadata: Dict[str, Any]


@dataclass
class GuardDecision:
    """Final guard decision with fallback options"""
    allowed: bool
    primary_reason: str
    fallback_options: List[str]
    requires_human_review: bool
    audit_data: Dict[str, Any]


class LlamaGuardService:
    """Enhanced Llama Guard service for comprehensive safety checking"""
    
    def __init__(self, config: LlamaGuardConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.cache = {}
        self._load_model()
    
    def _load_model(self):
        """Load Llama Guard model"""
        try:
            logger.info(f"Loading Llama Guard model: {self.config.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model_name,
                trust_remote_code=True,
                torch_dtype=getattr(torch, self.config.torch_dtype),
                device_map=self.config.device
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Llama Guard model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Llama Guard model: {e}")
            if not self.config.fallback_on_failure:
                raise
            self._initialize_fallback_models()
    
    def _initialize_fallback_models(self):
        """Initialize fallback safety models"""
        logger.warning("Using fallback safety models")
        self.fallback_patterns = {
            SafetyCategory.VIOLENCE: [
                r'\b(kill|murder|violence|attack|harm|hurt)\b',
                r'\b(weapon|gun|knife|bomb|explos)\w*\b'
            ],
            SafetyCategory.HATE: [
                r'\b(hate|discriminat|racist|sexist|homophobic)\b',
                r'\b(slur|offensive|derogatory)\b'
            ],
            SafetyCategory.SEXUAL: [
                r'\b(explicit|sexual|porn|adult|nsfw)\b',
                r'\b(inappropriate|offensive sexual)\b'
            ],
            SafetyCategory.SELF_HARM: [
                r'\b(suicide|self.harm|kill myself|end my life)\b',
                r'\b(depression|anxiety|mental health crisis)\b'
            ],
            SafetyCategory.ILLEGAL: [
                r'\b(illegal|criminal|fraud|scam|hack)\b',
                r'\b(drug|narcotic|substance abuse)\b'
            ],
            SafetyCategory.PRIVACY: [
                r'\b(password|secret|private.key|ssn|credit.card)\b',
                r'\b(personal.info|confidential|sensitive)\b'
            ]
        }
    
    async def analyze_input(self, query_request: QueryRequest) -> SafetyAnalysis:
        """Analyze input query for safety"""
        cache_key = f"input:{hash(query_request.query)}"
        
        if self.config.cache_results and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if datetime.now() - cached_result['timestamp'] < timedelta(minutes=self.config.cache_ttl_minutes):
                return cached_result['analysis']
        
        try:
            if self.model is not None:
                analysis = await self._analyze_with_llama_guard(query_request.query, "input")
            else:
                analysis = await self._analyze_with_fallback(query_request.query)
            
            if self.config.cache_results:
                self.cache[cache_key] = {
                    'analysis': analysis,
                    'timestamp': datetime.now()
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Input analysis failed: {e}")
            return SafetyAnalysis(
                is_safe=False,
                risk_scores={category: 0.8 for category in SafetyCategory},
                overall_risk=0.8,
                risk_level=RiskLevel.HIGH,
                reasoning=f"Safety analysis failed: {str(e)}",
                flagged_content=["analysis_failure"],
                suggestions=["Please try again later"],
                metadata={"error": str(e)}
            )
    
    async def analyze_output(self, generated_text: str, context: List[str] = None) -> SafetyAnalysis:
        """Analyze generated output for safety"""
        cache_key = f"output:{hash(generated_text)}"
        
        if self.config.cache_results and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if datetime.now() - cached_result['timestamp'] < timedelta(minutes=self.config.cache_ttl_minutes):
                return cached_result['analysis']
        
        try:
            if self.model is not None:
                analysis = await self._analyze_with_llama_guard(generated_text, "output")
            else:
                analysis = await self._analyze_with_fallback(generated_text)
            
            # Additional context-based analysis
            if context and self.config.enable_context_analysis:
                context_analysis = await self._analyze_context_consistency(generated_text, context)
                analysis.metadata.update(context_analysis)
            
            if self.config.cache_results:
                self.cache[cache_key] = {
                    'analysis': analysis,
                    'timestamp': datetime.now()
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Output analysis failed: {e}")
            return SafetyAnalysis(
                is_safe=False,
                risk_scores={category: 0.9 for category in SafetyCategory},
                overall_risk=0.9,
                risk_level=RiskLevel.CRITICAL,
                reasoning=f"Output safety analysis failed: {str(e)}",
                flagged_content=["analysis_failure"],
                suggestions=["Response blocked due to safety check failure"],
                metadata={"error": str(e)}
            )
    
    async def _analyze_with_llama_guard(self, text: str, content_type: str) -> SafetyAnalysis:
        """Analyze text using Llama Guard model"""
        try:
            # Prepare prompt for Llama Guard
            prompt = self._create_llama_guard_prompt(text, content_type)
            
            # Tokenize
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=self.config.max_length,
                truncation=True,
                padding=True
            ).to(self.model.device)
            
            # Get model predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.softmax(outputs.logits, dim=-1)
            
            # Parse predictions (simplified - actual implementation depends on Llama Guard format)
            risk_scores = self._parse_llama_guard_predictions(predictions[0])
            
            # Calculate overall risk
            overall_risk = max(risk_scores.values())
            risk_level = self._calculate_risk_level(overall_risk)
            
            # Determine safety
            is_safe = all(score < self.config.risk_thresholds[category] 
                         for category, score in risk_scores.items())
            
            # Generate reasoning and suggestions
            flagged_categories = [cat for cat, score in risk_scores.items() 
                                if score >= self.config.risk_thresholds[cat]]
            
            reasoning = self._generate_reasoning(flagged_categories, risk_scores)
            suggestions = self._generate_suggestions(flagged_categories)
            
            return SafetyAnalysis(
                is_safe=is_safe,
                risk_scores=risk_scores,
                overall_risk=overall_risk,
                risk_level=risk_level,
                reasoning=reasoning,
                flagged_content=flagged_categories,
                suggestions=suggestions,
                metadata={"model_used": "llama_guard", "content_type": content_type}
            )
            
        except Exception as e:
            logger.error(f"Llama Guard analysis failed: {e}")
            raise
    
    async def _analyze_with_fallback(self, text: str) -> SafetyAnalysis:
        """Analyze text using fallback regex patterns"""
        risk_scores = {}
        flagged_content = []
        
        text_lower = text.lower()
        
        for category, patterns in self.fallback_patterns.items():
            category_score = 0.0
            category_flags = []
            
            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    category_score += len(matches) * 0.2
                    category_flags.extend(matches)
            
            risk_scores[category] = min(category_score, 1.0)
            if category_flags:
                flagged_content.extend([f"{category.value}:{flag}" for flag in category_flags])
        
        overall_risk = max(risk_scores.values()) if risk_scores else 0.0
        risk_level = self._calculate_risk_level(overall_risk)
        
        is_safe = overall_risk < 0.5
        
        return SafetyAnalysis(
            is_safe=is_safe,
            risk_scores=risk_scores,
            overall_risk=overall_risk,
            risk_level=risk_level,
            reasoning="Fallback pattern-based analysis",
            flagged_content=flagged_content,
            suggestions=["Review content for safety concerns"] if not is_safe else [],
            metadata={"model_used": "fallback_patterns"}
        )
    
    async def _analyze_context_consistency(self, generated_text: str, context: List[str]) -> Dict[str, Any]:
        """Analyze consistency between generated text and context"""
        # Simple consistency check - can be enhanced with NLI models
        context_text = " ".join(context).lower()
        generated_lower = generated_text.lower()
        
        # Extract key terms from context
        context_terms = set(re.findall(r'\b\w{3,}\b', context_text))
        generated_terms = set(re.findall(r'\b\w{3,}\b', generated_lower))
        
        # Calculate overlap
        overlap = len(context_terms & generated_terms)
        coverage = overlap / len(context_terms) if context_terms else 0
        
        return {
            "context_coverage": coverage,
            "term_overlap": overlap,
            "consistency_score": min(coverage, 1.0),
            "potential_hallucination": coverage < 0.3
        }
    
    def _create_llama_guard_prompt(self, text: str, content_type: str) -> str:
        """Create prompt for Llama Guard"""
        if content_type == "input":
            return f"""[INST] Task: Classify the following user query for safety.

User Query: {text}

Classify the query for the following categories:
- Violence
- Hate speech
- Sexual content
- Self-harm
- Illegal activities
- Privacy violations
- Misinformation
- Toxicity

Respond with a JSON object containing risk scores (0-1) for each category. [/INST]"""
        else:
            return f"""[INST] Task: Classify the following AI-generated response for safety.

AI Response: {text}

Classify the response for the following categories:
- Violence
- Hate speech
- Sexual content
- Self-harm
- Illegal activities
- Privacy violations
- Misinformation
- Toxicity

Respond with a JSON object containing risk scores (0-1) for each category. [/INST]"""
    
    def _parse_llama_guard_predictions(self, predictions: torch.Tensor) -> Dict[SafetyCategory, float]:
        """Parse Llama Guard predictions into risk scores"""
        # This is a simplified implementation
        # Actual implementation depends on Llama Guard's output format
        scores = {}
        
        # Assuming predictions are logits for different safety categories
        # This would need to be adapted based on the actual model output
        for i, category in enumerate(SafetyCategory):
            if i < predictions.shape[-1]:
                scores[category] = float(torch.sigmoid(predictions[i]).item())
            else:
                scores[category] = 0.0
        
        return scores
    
    def _calculate_risk_level(self, overall_risk: float) -> RiskLevel:
        """Calculate risk level from overall risk score"""
        if overall_risk >= 0.8:
            return RiskLevel.CRITICAL
        elif overall_risk >= 0.6:
            return RiskLevel.HIGH
        elif overall_risk >= 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_reasoning(self, flagged_categories: List[SafetyCategory], 
                           risk_scores: Dict[SafetyCategory, float]) -> str:
        """Generate human-readable reasoning for safety decision"""
        if not flagged_categories:
            return "Content appears safe based on analysis"
        
        reasons = []
        for category in flagged_categories:
            score = risk_scores[category]
            reasons.append(f"High {category.value} risk detected (score: {score:.2f})")
        
        return "; ".join(reasons)
    
    def _generate_suggestions(self, flagged_categories: List[SafetyCategory]) -> List[str]:
        """Generate suggestions for improving content safety"""
        suggestions = []
        
        for category in flagged_categories:
            if category == SafetyCategory.VIOLENCE:
                suggestions.append("Remove violent language and imagery")
            elif category == SafetyCategory.HATE:
                suggestions.append("Ensure content is inclusive and respectful")
            elif category == SafetyCategory.SEXUAL:
                suggestions.append("Remove explicit sexual content")
            elif category == SafetyCategory.SELF_HARM:
                suggestions.append("Include mental health resources for self-harm content")
            elif category == SafetyCategory.ILLEGAL:
                suggestions.append("Remove references to illegal activities")
            elif category == SafetyCategory.PRIVACY:
                suggestions.append("Remove personal and sensitive information")
            elif category == SafetyCategory.MISINFORMATION:
                suggestions.append("Verify factual accuracy of claims")
            elif category == SafetyCategory.TOXICITY:
                suggestions.append("Improve tone to be more constructive")
        
        return suggestions
    
    def clear_cache(self):
        """Clear the analysis cache"""
        self.cache.clear()
        logger.info("Llama Guard cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_enabled": self.config.cache_results,
            "cache_ttl_minutes": self.config.cache_ttl_minutes
        }
