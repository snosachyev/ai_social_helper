"""RAG Pipeline Implementation"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
from dataclasses import dataclass

from shared.models.base import RetrievalResult, QueryRequest, QueryType

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG Pipeline configuration."""
    # Retrieval settings
    retrieval_top_k: int = 20
    min_similarity_score: float = 0.5
    max_context_length: int = 4000
    
    # Reranking settings
    use_reranking: bool = True
    rerank_top_k: int = 10
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Context settings
    context_window_size: int = 3
    max_chunks_per_document: int = 5
    
    # Diversity settings
    use_diversity_rerank: bool = True
    diversity_lambda: float = 0.3
    
    # Query expansion
    use_query_expansion: bool = True
    expansion_top_k: int = 5


class RAGPipeline:
    """Production-ready RAG pipeline with advanced features."""
    
    def __init__(self, embedding_client, vector_client, config: RAGConfig = None):
        self.embedding_client = embedding_client
        self.vector_client = vector_client
        self.config = config or RAGConfig()
        
        # Service URLs
        self.embedding_service_url = "http://embedding-service:8002"
        self.vector_service_url = "http://vector-service:8003"
    
    async def process_query(self, query_request: QueryRequest) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """Process query through full RAG pipeline."""
        pipeline_stats = {
            "stages": {},
            "total_time_ms": 0,
            "query_id": query_request.query_id
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Stage 1: Query preprocessing and expansion
            expanded_query, expansion_stats = await self._expand_query(query_request.query)
            pipeline_stats["stages"]["query_expansion"] = expansion_stats
            
            # Stage 2: Initial retrieval
            initial_results, retrieval_stats = await self._initial_retrieval(
                expanded_query, 
                query_request.top_k * 2  # Get more for reranking
            )
            pipeline_stats["stages"]["initial_retrieval"] = retrieval_stats
            
            # Stage 3: Filter by minimum score
            filtered_results = self._filter_by_score(initial_results)
            pipeline_stats["stages"]["score_filtering"] = {
                "input_count": len(initial_results),
                "output_count": len(filtered_results)
            }
            
            # Stage 4: Diversity-based reranking
            if self.config.use_diversity_rerank and len(filtered_results) > query_request.top_k:
                diverse_results, diversity_stats = await self._diversity_rerank(
                    filtered_results, 
                    query_request.top_k
                )
                pipeline_stats["stages"]["diversity_rerank"] = diversity_stats
            else:
                diverse_results = filtered_results
            
            # Stage 5: Cross-encoder reranking
            if self.config.use_reranking and len(diverse_results) > query_request.top_k:
                reranked_results, rerank_stats = await self._cross_encoder_rerank(
                    expanded_query,
                    diverse_results,
                    query_request.top_k
                )
                pipeline_stats["stages"]["cross_encoder_rerank"] = rerank_stats
            else:
                reranked_results = diverse_results[:query_request.top_k]
            
            # Stage 6: Context optimization
            optimized_results, context_stats = await self._optimize_context(
                reranked_results,
                query_request.query
            )
            pipeline_stats["stages"]["context_optimization"] = context_stats
            
            # Stage 7: Final filtering
            final_results = self._apply_final_filters(
                optimized_results,
                query_request.filters
            )
            pipeline_stats["stages"]["final_filtering"] = {
                "input_count": len(optimized_results),
                "output_count": len(final_results)
            }
            
            # Calculate total time
            pipeline_stats["total_time_ms"] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            logger.info(f"RAG pipeline completed for query {query_request.query_id}: {pipeline_stats}")
            
            return final_results[:query_request.top_k], pipeline_stats
            
        except Exception as e:
            logger.error(f"RAG pipeline failed for query {query_request.query_id}: {e}")
            raise
    
    async def _expand_query(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """Expand query with synonyms and related terms."""
        start_time = datetime.utcnow()
        
        if not self.config.use_query_expansion:
            return query, {"expanded": False, "time_ms": 0}
        
        try:
            # Simple query expansion using embedding similarity
            # In production, would use more sophisticated techniques
            
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query)
            
            # Search for similar queries in history (simplified)
            # This would normally query a query history index
            expanded_terms = []
            
            # For now, return original query
            expanded_query = query
            
            time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return expanded_query, {
                "expanded": len(expanded_terms) > 0,
                "expanded_terms": expanded_terms,
                "time_ms": time_ms
            }
            
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return query, {"expanded": False, "error": str(e), "time_ms": 0}
    
    async def _initial_retrieval(self, query: str, top_k: int) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """Initial vector retrieval."""
        start_time = datetime.utcnow()
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query)
            
            # Search vector database
            response = await self.vector_client.post(
                f"{self.vector_service_url}/vectors/search",
                json={
                    "query_embedding": query_embedding,
                    "top_k": top_k
                }
            )
            response.raise_for_status()
            
            search_results = response.json()
            results = [RetrievalResult(**result) for result in search_results]
            
            time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return results, {
                "retrieved_count": len(results),
                "time_ms": time_ms
            }
            
        except Exception as e:
            logger.error(f"Initial retrieval failed: {e}")
            raise
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query."""
        response = await self.embedding_client.post(
            f"{self.embedding_service_url}/embeddings/generate",
            json={
                "chunk_id": f"query_{datetime.utcnow().timestamp()}",
                "text": query
            }
        )
        response.raise_for_status()
        
        embedding_data = response.json()
        return embedding_data["embedding"]
    
    def _filter_by_score(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Filter results by minimum similarity score."""
        return [
            result for result in results 
            if result.score >= self.config.min_similarity_score
        ]
    
    async def _diversity_rerank(self, results: List[RetrievalResult], top_k: int) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """Apply Maximal Marginal Relevance (MMR) for diversity."""
        start_time = datetime.utcnow()
        
        try:
            if len(results) <= top_k:
                return results, {"diversified": False, "time_ms": 0}
            
            # Simplified MMR implementation
            selected = [results[0]]  # Start with highest scoring result
            remaining = results[1:]
            
            while len(selected) < top_k and remaining:
                # Find result with maximal marginal relevance
                best_idx = 0
                best_score = -1
                
                for i, candidate in enumerate(remaining):
                    # Calculate similarity to already selected items
                    min_sim_to_selected = min([
                        self._calculate_similarity(candidate, selected_item)
                        for selected_item in selected
                    ])
                    
                    # MMR score: λ * relevance - (1-λ) * max_similarity
                    mmr_score = (
                        self.config.diversity_lambda * candidate.score - 
                        (1 - self.config.diversity_lambda) * min_sim_to_selected
                    )
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = i
                
                selected.append(remaining.pop(best_idx))
            
            time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return selected, {
                "diversified": True,
                "lambda": self.config.diversity_lambda,
                "time_ms": time_ms
            }
            
        except Exception as e:
            logger.warning(f"Diversity reranking failed: {e}")
            return results[:top_k], {"diversified": False, "error": str(e), "time_ms": 0}
    
    async def _cross_encoder_rerank(self, query: str, results: List[RetrievalResult], top_k: int) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """Rerank results using cross-encoder model."""
        start_time = datetime.utcnow()
        
        try:
            # In production, would use actual cross-encoder model
            # For now, implement a simplified text-based reranking
            
            scored_results = []
            for result in results:
                # Calculate text-based relevance score
                relevance_score = self._calculate_text_relevance(query, result.text)
                
                # Combine with original score
                combined_score = 0.6 * result.score + 0.4 * relevance_score
                result.score = combined_score
                scored_results.append(result)
            
            # Sort by combined score
            scored_results.sort(key=lambda x: x.score, reverse=True)
            
            time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return scored_results[:top_k], {
                "reranked": True,
                "model": self.config.rerank_model,
                "time_ms": time_ms
            }
            
        except Exception as e:
            logger.warning(f"Cross-encoder reranking failed: {e}")
            return results[:top_k], {"reranked": False, "error": str(e), "time_ms": 0}
    
    def _calculate_similarity(self, result1: RetrievalResult, result2: RetrievalResult) -> float:
        """Calculate similarity between two results."""
        # Simple text similarity (Jaccard)
        words1 = set(result1.text.lower().split())
        words2 = set(result2.text.lower().split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_text_relevance(self, query: str, text: str) -> float:
        """Calculate text-based relevance score."""
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        # Calculate coverage and precision
        intersection = query_words.intersection(text_words)
        
        if not query_words:
            return 0.0
        
        coverage = len(intersection) / len(query_words)  # How many query terms are covered
        precision = len(intersection) / len(text_words) if text_words else 0.0  # How specific the match is
        
        return (coverage + precision) / 2
    
    async def _optimize_context(self, results: List[RetrievalResult], query: str) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """Optimize context for better generation."""
        start_time = datetime.utcnow()
        
        try:
            # Group results by document
            document_groups = {}
            for result in results:
                doc_id = result.metadata.get("document_id", "unknown")
                if doc_id not in document_groups:
                    document_groups[doc_id] = []
                document_groups[doc_id].append(result)
            
            # Select best chunks from each document
            optimized_results = []
            total_length = 0
            
            for doc_id, doc_results in document_groups.items():
                # Sort by score within document
                doc_results.sort(key=lambda x: x.score, reverse=True)
                
                # Take top chunks from this document
                chunks_taken = 0
                for result in doc_results:
                    if chunks_taken >= self.config.max_chunks_per_document:
                        break
                    
                    if total_length + len(result.text) > self.config.max_context_length:
                        break
                    
                    optimized_results.append(result)
                    total_length += len(result.text)
                    chunks_taken += 1
            
            # Sort final results by score
            optimized_results.sort(key=lambda x: x.score, reverse=True)
            
            time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return optimized_results, {
                "optimized": True,
                "documents_used": len(document_groups),
                "total_length": total_length,
                "time_ms": time_ms
            }
            
        except Exception as e:
            logger.warning(f"Context optimization failed: {e}")
            return results, {"optimized": False, "error": str(e), "time_ms": 0}
    
    def _apply_final_filters(self, results: List[RetrievalResult], filters: Dict[str, Any]) -> List[RetrievalResult]:
        """Apply final filters to results."""
        if not filters:
            return results
        
        filtered_results = []
        
        for result in results:
            # Document type filter
            if "document_type" in filters:
                doc_type = result.metadata.get("document_type")
                if doc_type != filters["document_type"]:
                    continue
            
            # Date range filter
            if "date_range" in filters:
                created_at = result.metadata.get("created_at")
                if created_at:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    start_date = filters["date_range"].get("start")
                    end_date = filters["date_range"].get("end")
                    
                    if start_date and created_date < start_date:
                        continue
                    if end_date and created_date > end_date:
                        continue
            
            # Source filter
            if "source" in filters:
                source = result.metadata.get("source")
                if source != filters["source"]:
                    continue
            
            filtered_results.append(result)
        
        return filtered_results
