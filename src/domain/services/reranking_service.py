"""Reranking domain service"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Protocol, runtime_checkable
import logging
import math
from collections import Counter

from ..entities.embedding import RetrievalResult


logger = logging.getLogger(__name__)


@runtime_checkable
class Reranker(Protocol):
    """Protocol for reranking implementations"""
    
    async def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank results based on query"""
        ...


class HybridReranker:
    """Hybrid reranking implementation combining multiple signals"""
    
    def __init__(self, config: "RerankingConfig" = None):
        self.config = config or RerankingConfig()
    
    async def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Apply hybrid reranking using multiple signals"""
        try:
            if not results:
                return results
            
            # Calculate different similarity scores
            reranked_results = []
            for result in results:
                # Text similarity (Jaccard)
                text_sim = self._calculate_jaccard_similarity(query, result.text)
                
                # TF-IDF similarity
                tfidf_sim = self._calculate_tfidf_similarity(query, result.text)
                
                # Length penalty (prefer concise answers)
                length_penalty = self._calculate_length_penalty(result.text)
                
                # Combine scores with weights
                combined_score = (
                    self.config.vector_weight * result.score +
                    self.config.text_weight * text_sim +
                    self.config.tfidf_weight * tfidf_sim +
                    self.config.length_weight * length_penalty
                )
                
                # Create new result with combined score
                reranked_result = RetrievalResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    text=result.text,
                    score=min(max(combined_score, 0.0), 1.0),  # Clamp to [0,1]
                    metadata={
                        **result.metadata,
                        "original_score": result.score,
                        "text_similarity": text_sim,
                        "tfidf_similarity": tfidf_sim,
                        "reranked": True
                    }
                )
                reranked_results.append(reranked_result)
            
            # Sort by combined score
            reranked_results.sort(key=lambda x: x.score, reverse=True)
            
            logger.info(f"Reranked {len(results)} results")
            return reranked_results
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Return original results if reranking fails
            return results
    
    def _calculate_jaccard_similarity(self, query: str, text: str) -> float:
        """Calculate Jaccard similarity between query and text"""
        try:
            query_words = set(self._tokenize(query.lower()))
            text_words = set(self._tokenize(text.lower()))
            
            intersection = query_words.intersection(text_words)
            union = query_words.union(text_words)
            
            if not union:
                return 0.0
            
            return len(intersection) / len(union)
            
        except Exception:
            return 0.0
    
    def _calculate_tfidf_similarity(self, query: str, text: str) -> float:
        """Calculate simplified TF-IDF similarity"""
        try:
            query_tokens = self._tokenize(query.lower())
            text_tokens = self._tokenize(text.lower())
            
            if not query_tokens or not text_tokens:
                return 0.0
            
            # Calculate TF for text
            text_tf = Counter(text_tokens)
            total_text_tokens = len(text_tokens)
            
            # Calculate IDF (simplified - assuming corpus of 1 document)
            # In production, would use actual corpus statistics
            query_idf = {token: 1.0 for token in query_tokens}
            
            # Calculate TF-IDF vectors
            query_tfidf = {}
            text_tfidf = {}
            
            for token in set(query_tokens + text_tokens):
                query_tfidf[token] = (query_tokens.count(token) / len(query_tokens)) * query_idf.get(token, 1.0)
                text_tfidf[token] = (text_tf.get(token, 0) / total_text_tokens) * query_idf.get(token, 1.0)
            
            # Calculate cosine similarity
            return self._cosine_similarity(query_tfidf, text_tfidf)
            
        except Exception:
            return 0.0
    
    def _calculate_length_penalty(self, text: str) -> float:
        """Calculate length penalty (prefer answers of reasonable length)"""
        text_length = len(text)
        
        if text_length < self.config.min_text_length:
            # Penalty for too short
            return text_length / self.config.min_text_length
        elif text_length > self.config.max_text_length:
            # Penalty for too long
            return max(0.0, 1.0 - (text_length - self.config.max_text_length) / self.config.max_text_length)
        else:
            # No penalty for optimal length
            return 1.0
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # In production, would use proper tokenizer
        return text.split()
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Get common terms
            common_terms = set(vec1.keys()) & set(vec2.keys())
            
            if not common_terms:
                return 0.0
            
            # Calculate dot product
            dot_product = sum(vec1[term] * vec2[term] for term in common_terms)
            
            # Calculate magnitudes
            mag1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
            mag2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
            
            if mag1 == 0 or mag2 == 0:
                return 0.0
            
            return dot_product / (mag1 * mag2)
            
        except Exception:
            return 0.0


class CrossEncoderReranker:
    """Cross-encoder based reranking (placeholder for future implementation)"""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None  # Would load actual cross-encoder model
    
    async def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank using cross-encoder model"""
        # Placeholder implementation
        # In production, would load and use actual cross-encoder model
        logger.info(f"Cross-encoder reranking with model: {self.model_name}")
        return results


@dataclass
class RerankingConfig:
    """Configuration for reranking service"""
    vector_weight: float = 0.5
    text_weight: float = 0.3
    tfidf_weight: float = 0.15
    length_weight: float = 0.05
    min_text_length: int = 50
    max_text_length: int = 1000
    enable_cross_encoder: bool = False
