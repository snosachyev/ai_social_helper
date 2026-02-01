"""Hallucination Detection Service for RAG System"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio
import re
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..entities.query import QueryRequest, GenerationRequest, RetrievalResult
from ..entities.document import Document, TextChunk


logger = logging.getLogger(__name__)


class HallucinationType(Enum):
    """Types of hallucinations to detect"""
    FACTUAL = "factual"
    CONTRADICTORY = "contradictory"
    SPECULATION = "speculation"
    SOURCELESS = "sourceless"
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    CAUSAL = "causal"


class ConfidenceLevel(Enum):
    """Confidence levels for hallucination detection"""
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5


@dataclass
class HallucinationDetectionConfig:
    """Configuration for hallucination detection"""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    similarity_threshold: float = 0.3
    factual_consistency_threshold: float = 0.5
    numerical_variance_threshold: float = 0.1
    enable_semantic_analysis: bool = True
    enable_factual_verification: bool = True
    enable_numerical_checking: bool = True
    enable_source_attribution: bool = True
    max_entities_per_analysis: int = 50
    confidence_threshold: float = 0.7


@dataclass
class HallucinationResult:
    """Result of hallucination analysis"""
    is_hallucinated: bool
    confidence_score: float
    confidence_level: ConfidenceLevel
    hallucination_types: List[HallucinationType]
    problematic_segments: List[str]
    source_coverage: float
    factual_consistency: float
    semantic_similarity: float
    explanations: List[str]
    suggestions: List[str]
    metadata: Dict[str, Any]


@dataclass
class FactClaim:
    """Represents a factual claim extracted from text"""
    claim: str
    entities: List[str]
    claim_type: str
    confidence: float
    source_snippets: List[str]
    verification_status: str


class HallucinationDetector:
    """Advanced hallucination detection service"""
    
    def __init__(self, config: HallucinationDetectionConfig):
        self.config = config
        self.embedding_model = None
        self._load_models()
    
    def _load_models(self):
        """Load required models"""
        try:
            logger.info("Loading embedding model for hallucination detection")
            self.embedding_model = SentenceTransformer(self.config.embedding_model)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    async def detect_hallucination(
        self, 
        query: str, 
        generated_response: str, 
        retrieved_context: List[RetrievalResult]
    ) -> HallucinationResult:
        """Main method to detect hallucinations in generated response"""
        try:
            # Extract context text
            context_texts = [result.text for result in retrieved_context]
            context_combined = " ".join(context_texts)
            
            # Perform multiple analyses
            semantic_analysis = await self._analyze_semantic_similarity(
                generated_response, context_combined
            )
            
            factual_analysis = await self._analyze_factual_consistency(
                generated_response, context_texts
            )
            
            source_analysis = await self._analyze_source_attribution(
                generated_response, context_texts
            )
            
            numerical_analysis = await self._analyze_numerical_consistency(
                generated_response, context_texts
            )
            
            # Combine results
            hallucination_types = []
            problematic_segments = []
            explanations = []
            
            # Check semantic similarity
            if semantic_analysis['similarity'] < self.config.similarity_threshold:
                hallucination_types.append(HallucinationType.FACTUAL)
                problematic_segments.extend(semantic_analysis['low_similarity_segments'])
                explanations.append(f"Low semantic similarity with sources ({semantic_analysis['similarity']:.2f})")
            
            # Check factual consistency
            if factual_analysis['consistency_score'] < self.config.factual_consistency_threshold:
                hallucination_types.append(HallucinationType.CONTRADICTORY)
                problematic_segments.extend(factual_analysis['contradictory_claims'])
                explanations.append(f"Factual inconsistencies detected ({factual_analysis['consistency_score']:.2f})")
            
            # Check source coverage
            if source_analysis['coverage'] < 0.5:
                hallucination_types.append(HallucinationType.SOURCELESS)
                problematic_segments.extend(source_analysis['unattributed_segments'])
                explanations.append(f"Low source attribution ({source_analysis['coverage']:.2f})")
            
            # Check numerical consistency
            if numerical_analysis['has_inconsistencies']:
                hallucination_types.append(HallucinationType.NUMERICAL)
                problematic_segments.extend(numerical_analysis['inconsistent_numbers'])
                explanations.append("Numerical inconsistencies detected")
            
            # Calculate overall confidence
            confidence_score = self._calculate_overall_confidence(
                semantic_analysis, factual_analysis, source_analysis, numerical_analysis
            )
            
            confidence_level = self._get_confidence_level(confidence_score)
            
            # Generate suggestions
            suggestions = self._generate_suggestions(hallucination_types, explanations)
            
            is_hallucinated = len(hallucination_types) > 0 and confidence_score > self.config.confidence_threshold
            
            return HallucinationResult(
                is_hallucinated=is_hallucinated,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                hallucination_types=hallucination_types,
                problematic_segments=problematic_segments,
                source_coverage=source_analysis['coverage'],
                factual_consistency=factual_analysis['consistency_score'],
                semantic_similarity=semantic_analysis['similarity'],
                explanations=explanations,
                suggestions=suggestions,
                metadata={
                    "query": query,
                    "analysis_timestamp": datetime.now().isoformat(),
                    "context_count": len(context_texts),
                    "response_length": len(generated_response)
                }
            )
            
        except Exception as e:
            logger.error(f"Hallucination detection failed: {e}")
            return HallucinationResult(
                is_hallucinated=True,
                confidence_score=0.9,
                confidence_level=ConfidenceLevel.VERY_HIGH,
                hallucination_types=[HallucinationType.FACTUAL],
                problematic_segments=[generated_response],
                source_coverage=0.0,
                factual_consistency=0.0,
                semantic_similarity=0.0,
                explanations=[f"Detection failed: {str(e)}"],
                suggestions=["Manual review required due to detection failure"],
                metadata={"error": str(e)}
            )
    
    async def _analyze_semantic_similarity(
        self, 
        response: str, 
        context: str
    ) -> Dict[str, Any]:
        """Analyze semantic similarity between response and context"""
        try:
            # Split response into sentences
            sentences = re.split(r'[.!?]+', response)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return {"similarity": 0.0, "low_similarity_segments": []}
            
            # Get embeddings
            response_embeddings = self.embedding_model.encode(sentences)
            context_embedding = self.embedding_model.encode([context])
            
            # Calculate similarities
            similarities = cosine_similarity(response_embeddings, context_embedding)
            
            # Find low similarity segments
            low_similarity_threshold = self.config.similarity_threshold
            low_similarity_segments = [
                sentences[i] for i, sim in enumerate(similarities.flatten())
                if sim < low_similarity_threshold
            ]
            
            overall_similarity = float(np.mean(similarities))
            
            return {
                "similarity": overall_similarity,
                "low_similarity_segments": low_similarity_segments,
                "sentence_similarities": similarities.flatten().tolist()
            }
            
        except Exception as e:
            logger.error(f"Semantic similarity analysis failed: {e}")
            return {"similarity": 0.0, "low_similarity_segments": []}
    
    async def _analyze_factual_consistency(
        self, 
        response: str, 
        context_texts: List[str]
    ) -> Dict[str, Any]:
        """Analyze factual consistency between response and context"""
        try:
            # Extract claims from response
            response_claims = await self._extract_factual_claims(response)
            
            contradictory_claims = []
            verified_claims = 0
            
            for claim in response_claims:
                # Check if claim is supported by context
                is_supported = await self._verify_claim_against_context(
                    claim, context_texts
                )
                
                if not is_supported:
                    contradictory_claims.append(claim.claim)
                else:
                    verified_claims += 1
            
            consistency_score = verified_claims / len(response_claims) if response_claims else 0.0
            
            return {
                "consistency_score": consistency_score,
                "contradictory_claims": contradictory_claims,
                "total_claims": len(response_claims),
                "verified_claims": verified_claims
            }
            
        except Exception as e:
            logger.error(f"Factual consistency analysis failed: {e}")
            return {"consistency_score": 0.0, "contradictory_claims": []}
    
    async def _analyze_source_attribution(
        self, 
        response: str, 
        context_texts: List[str]
    ) -> Dict[str, Any]:
        """Analyze how well response attributes to sources"""
        try:
            # Split response into segments
            segments = re.split(r'[.!?]+', response)
            segments = [s.strip() for s in segments if s.strip()]
            
            attributed_segments = 0
            unattributed_segments = []
            
            for segment in segments:
                # Check if segment has source support
                has_source = await self._check_segment_source_support(
                    segment, context_texts
                )
                
                if has_source:
                    attributed_segments += 1
                else:
                    unattributed_segments.append(segment)
            
            coverage = attributed_segments / len(segments) if segments else 0.0
            
            return {
                "coverage": coverage,
                "attributed_segments": attributed_segments,
                "unattributed_segments": unattributed_segments,
                "total_segments": len(segments)
            }
            
        except Exception as e:
            logger.error(f"Source attribution analysis failed: {e}")
            return {"coverage": 0.0, "unattributed_segments": []}
    
    async def _analyze_numerical_consistency(
        self, 
        response: str, 
        context_texts: List[str]
    ) -> Dict[str, Any]:
        """Analyze numerical consistency between response and context"""
        try:
            # Extract numbers from response
            response_numbers = await self._extract_numbers(response)
            
            # Extract numbers from context
            context_numbers = await self._extract_numbers(" ".join(context_texts))
            
            inconsistent_numbers = []
            
            for resp_num in response_numbers:
                # Find similar numbers in context
                context_matches = [
                    ctx_num for ctx_num in context_numbers
                    if abs(resp_num['value'] - ctx_num['value']) <= self.config.numerical_variance_threshold
                ]
                
                if not context_matches:
                    inconsistent_numbers.append(resp_num['text'])
            
            return {
                "has_inconsistencies": len(inconsistent_numbers) > 0,
                "inconsistent_numbers": inconsistent_numbers,
                "response_numbers": len(response_numbers),
                "context_numbers": len(context_numbers)
            }
            
        except Exception as e:
            logger.error(f"Numerical consistency analysis failed: {e}")
            return {"has_inconsistencies": True, "inconsistent_numbers": []}
    
    async def _extract_factual_claims(self, text: str) -> List[FactClaim]:
        """Extract factual claims from text"""
        # Simplified claim extraction - can be enhanced with NLP models
        claims = []
        
        # Extract sentences with entities
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Filter out very short sentences
                # Simple entity extraction (numbers, dates, proper nouns)
                entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b\d+(?:\.\d+)?\b', sentence)
                
                if entities:
                    claim = FactClaim(
                        claim=sentence,
                        entities=entities,
                        claim_type="factual",
                        confidence=0.7,
                        source_snippets=[],
                        verification_status="unverified"
                    )
                    claims.append(claim)
        
        return claims[:self.config.max_entities_per_analysis]
    
    async def _verify_claim_against_context(
        self, 
        claim: FactClaim, 
        context_texts: List[str]
    ) -> bool:
        """Verify if a claim is supported by context"""
        claim_embedding = self.embedding_model.encode([claim.claim])
        
        for context in context_texts:
            context_embedding = self.embedding_model.encode([context])
            similarity = cosine_similarity(claim_embedding, context_embedding)[0][0]
            
            if similarity > 0.7:  # High similarity threshold for verification
                return True
        
        return False
    
    async def _check_segment_source_support(
        self, 
        segment: str, 
        context_texts: List[str]
    ) -> bool:
        """Check if a segment has support in sources"""
        segment_embedding = self.embedding_model.encode([segment])
        
        for context in context_texts:
            context_embedding = self.embedding_model.encode([context])
            similarity = cosine_similarity(segment_embedding, context_embedding)[0][0]
            
            if similarity > 0.5:  # Moderate threshold for source support
                return True
        
        return False
    
    async def _extract_numbers(self, text: str) -> List[Dict[str, Any]]:
        """Extract numbers with context"""
        number_pattern = r'(?P<text>\b(?P<value>\d+(?:\.\d+)?)\b(?:\s*(?:%|percent|dollars?|USD|years?|days?|months?))?)'
        
        matches = []
        for match in re.finditer(number_pattern, text):
            matches.append({
                'text': match.group('text'),
                'value': float(match.group('value')),
                'position': match.start()
            })
        
        return matches
    
    def _calculate_overall_confidence(
        self, 
        semantic_analysis: Dict, 
        factual_analysis: Dict, 
        source_analysis: Dict, 
        numerical_analysis: Dict
    ) -> float:
        """Calculate overall confidence score for hallucination detection"""
        weights = {
            'semantic': 0.3,
            'factual': 0.3,
            'source': 0.2,
            'numerical': 0.2
        }
        
        semantic_score = 1.0 - semantic_analysis['similarity']
        factual_score = 1.0 - factual_analysis['consistency_score']
        source_score = 1.0 - source_analysis['coverage']
        numerical_score = 1.0 if numerical_analysis['has_inconsistencies'] else 0.0
        
        overall_confidence = (
            weights['semantic'] * semantic_score +
            weights['factual'] * factual_score +
            weights['source'] * source_score +
            weights['numerical'] * numerical_score
        )
        
        return float(overall_confidence)
    
    def _get_confidence_level(self, confidence_score: float) -> ConfidenceLevel:
        """Convert confidence score to confidence level"""
        if confidence_score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _generate_suggestions(
        self, 
        hallucination_types: List[HallucinationType], 
        explanations: List[str]
    ) -> List[str]:
        """Generate suggestions to reduce hallucination"""
        suggestions = []
        
        for hallucination_type in hallucination_types:
            if hallucination_type == HallucinationType.FACTUAL:
                suggestions.append("Verify facts against reliable sources")
                suggestions.append("Add citations for factual claims")
            elif hallucination_type == HallucinationType.CONTRADICTORY:
                suggestions.append("Check for internal consistency")
                suggestions.append("Review conflicting statements")
            elif hallucination_type == HallucinationType.SOURCELESS:
                suggestions.append("Ensure all claims are supported by retrieved context")
                suggestions.append("Add source attribution for statements")
            elif hallucination_type == HallucinationType.NUMERICAL:
                suggestions.append("Double-check all numbers and statistics")
                suggestions.append("Verify numerical data against sources")
            elif hallucination_type == HallucinationType.SPECULATION:
                suggestions.append("Clearly mark speculative content")
                suggestions.append("Avoid presenting speculation as fact")
        
        # Add general suggestions
        if len(hallucination_types) > 1:
            suggestions.append("Consider reducing response complexity")
            suggestions.append("Focus on well-supported information")
        
        return suggestions
