"""Mock service implementations for testing"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import asyncio
from datetime import datetime

from ...domain.entities.query import QueryRequest, RetrievalResult, GenerationRequest, GenerationResponse
from ...domain.entities.embedding import EmbeddingVector
from ...domain.services.retrieval_service import EmbeddingProvider, VectorStore, Reranker
from ...domain.services.guard_service import Guard, GuardResult, GuardConfig
from ...domain.services.reranking_service import HybridReranker


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing"""
    
    def __init__(self):
        self.embeddings: Dict[str, List[float]] = {}
        self.call_count = 0
        self.last_call_args = {}
        self.generate_embedding_delay = 0.0
        self.generate_batch_delay = 0.0
        self.should_fail = False
        self.failure_message = "Mock embedding generation failed"
    
    async def generate_embedding(self, text: str, model_name: str) -> EmbeddingVector:
        self.call_count += 1
        self.last_call_args['generate_embedding'] = {'text': text, 'model_name': model_name}
        
        if self.generate_embedding_delay > 0:
            await asyncio.sleep(self.generate_embedding_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Generate deterministic mock embedding based on text
        embedding = self._generate_mock_embedding(text)
        
        return EmbeddingVector(
            chunk_id=UUID(),  # Will be set by caller
            embedding=embedding,
            model_name=model_name,
            dimension=len(embedding)
        )
    
    async def generate_batch_embeddings(self, texts: List[str], model_name: str) -> List[EmbeddingVector]:
        self.call_count += 1
        self.last_call_args['generate_batch_embeddings'] = {'texts': texts, 'model_name': model_name}
        
        if self.generate_batch_delay > 0:
            await asyncio.sleep(self.generate_batch_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        embeddings = []
        for text in texts:
            embedding = self._generate_mock_embedding(text)
            vector = EmbeddingVector(
                chunk_id=UUID(),  # Will be set by caller
                embedding=embedding,
                model_name=model_name,
                dimension=len(embedding)
            )
            embeddings.append(vector)
        
        return embeddings
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding"""
        # Create a simple hash-based embedding for reproducibility
        import hashlib
        
        # Generate hash of text
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Convert hash to float values
        embedding = []
        for i in range(0, len(text_hash), 2):
            hex_pair = text_hash[i:i+2]
            value = int(hex_pair, 16) / 255.0  # Normalize to [0, 1]
            # Convert to [-1, 1] range
            embedding.append((value - 0.5) * 2)
        
        # Pad or truncate to standard dimension
        target_dim = 384
        if len(embedding) < target_dim:
            embedding.extend([0.0] * (target_dim - len(embedding)))
        else:
            embedding = embedding[:target_dim]
        
        return embedding
    
    def set_embedding_delay(self, delay: float):
        """Set delay for embedding generation"""
        self.generate_embedding_delay = delay
    
    def set_batch_delay(self, delay: float):
        """Set delay for batch embedding generation"""
        self.generate_batch_delay = delay
    
    def set_failure(self, should_fail: bool, message: str = "Mock embedding generation failed"):
        """Set whether to simulate failure"""
        self.should_fail = should_fail
        self.failure_message = message
    
    def reset(self):
        """Reset mock state"""
        self.embeddings.clear()
        self.call_count = 0
        self.last_call_args.clear()
        self.generate_embedding_delay = 0.0
        self.generate_batch_delay = 0.0
        self.should_fail = False


class MockVectorStore(VectorStore):
    """Mock vector store for testing"""
    
    def __init__(self):
        self.vectors: Dict[str, EmbeddingVector] = {}
        self.search_results: List[RetrievalResult] = []
        self.call_count = 0
        self.last_call_args = {}
        self.add_vectors_delay = 0.0
        self.search_delay = 0.0
        self.should_fail = False
        self.failure_message = "Mock vector store operation failed"
    
    async def add_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        self.call_count += 1
        self.last_call_args['add_vectors'] = vectors
        
        if self.add_vectors_delay > 0:
            await asyncio.sleep(self.add_vectors_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        for vector in vectors:
            self.vectors[str(vector.vector_id)] = vector
        
        return True
    
    async def search(self, query_embedding: EmbeddingVector, top_k: int, filters: dict = None) -> List[RetrievalResult]:
        self.call_count += 1
        self.last_call_args['search'] = {
            'query_embedding': query_embedding,
            'top_k': top_k,
            'filters': filters
        }
        
        if self.search_delay > 0:
            await asyncio.sleep(self.search_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Return predefined results if available
        if self.search_results:
            return self.search_results[:top_k]
        
        # Generate mock results
        results = []
        for i, (vector_id, stored_vector) in enumerate(list(self.vectors.items())[:top_k]):
            # Calculate mock similarity
            similarity = self._calculate_mock_similarity(query_embedding.embedding, stored_vector.embedding)
            
            result = RetrievalResult(
                chunk_id=stored_vector.chunk_id,
                document_id=UUID(),  # Mock document ID
                text=f"Mock text for chunk {stored_vector.chunk_id}",
                score=similarity,
                metadata={"mock": True, "vector_id": vector_id}
            )
            results.append(result)
        
        # Sort by similarity score
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    async def delete_vector(self, vector_id: str) -> bool:
        self.call_count += 1
        self.last_call_args['delete_vector'] = vector_id
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        if vector_id in self.vectors:
            del self.vectors[vector_id]
            return True
        return False
    
    def _calculate_mock_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Calculate mock similarity score"""
        if len(emb1) != len(emb2):
            return 0.5  # Default similarity
        
        # Simple dot product similarity
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        magnitude1 = sum(a * a for a in emb1) ** 0.5
        magnitude2 = sum(b * b for b in emb2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
    
    def set_search_results(self, results: List[RetrievalResult]):
        """Set predefined search results"""
        self.search_results = results
    
    def set_add_vectors_delay(self, delay: float):
        """Set delay for add vectors operation"""
        self.add_vectors_delay = delay
    
    def set_search_delay(self, delay: float):
        """Set delay for search operation"""
        self.search_delay = delay
    
    def set_failure(self, should_fail: bool, message: str = "Mock vector store operation failed"):
        """Set whether to simulate failure"""
        self.should_fail = should_fail
        self.failure_message = message
    
    def reset(self):
        """Reset mock state"""
        self.vectors.clear()
        self.search_results.clear()
        self.call_count = 0
        self.last_call_args.clear()
        self.add_vectors_delay = 0.0
        self.search_delay = 0.0
        self.should_fail = False


class MockReranker(Reranker):
    """Mock reranker for testing"""
    
    def __init__(self):
        self.call_count = 0
        self.last_call_args = {}
        self.rerank_delay = 0.0
        self.should_fail = False
        self.failure_message = "Mock reranking failed"
        self.reranking_function = None
    
    async def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        self.call_count += 1
        self.last_call_args['rerank'] = {'query': query, 'results': results}
        
        if self.rerank_delay > 0:
            await asyncio.sleep(self.rerank_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Use custom reranking function if provided
        if self.reranking_function:
            return self.reranking_function(query, results)
        
        # Default mock reranking: just reverse the order and adjust scores
        reranked = []
        for i, result in enumerate(reversed(results)):
            new_result = RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                text=result.text,
                score=0.9 - i * 0.1,  # Decreasing scores
                metadata={**result.metadata, "reranked": True, "mock": True}
            )
            reranked.append(new_result)
        
        return reranked
    
    def set_reranking_function(self, func):
        """Set custom reranking function"""
        self.reranking_function = func
    
    def set_rerank_delay(self, delay: float):
        """Set delay for reranking operation"""
        self.rerank_delay = delay
    
    def set_failure(self, should_fail: bool, message: str = "Mock reranking failed"):
        """Set whether to simulate failure"""
        self.should_fail = should_fail
        self.failure_message = message
    
    def reset(self):
        """Reset mock state"""
        self.call_count = 0
        self.last_call_args.clear()
        self.rerank_delay = 0.0
        self.should_fail = False
        self.reranking_function = None


class MockGuard(Guard):
    """Mock guard for testing"""
    
    def __init__(self, default_allow: bool = True):
        self.default_allow = default_allow
        self.call_count = 0
        self.last_call_args = {}
        self.validation_delay = 0.0
        self.should_fail = False
        self.failure_message = "Mock guard validation failed"
        self.query_results: Dict[str, GuardResult] = {}
        self.generation_results: Dict[str, GuardResult] = {}
    
    async def validate_query(self, query_request: QueryRequest) -> GuardResult:
        self.call_count += 1
        self.last_call_args['validate_query'] = query_request
        
        if self.validation_delay > 0:
            await asyncio.sleep(self.validation_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Check for predefined result
        query_key = str(query_request.query_id)
        if query_key in self.query_results:
            return self.query_results[query_key]
        
        # Default result
        return GuardResult(
            is_allowed=self.default_allow,
            reason="Mock guard validation passed" if self.default_allow else "Mock guard validation rejected",
            risk_score=0.1 if self.default_allow else 0.9,
            metadata={"mock": True}
        )
    
    async def validate_generation(self, generation_request: GenerationRequest) -> GuardResult:
        self.call_count += 1
        self.last_call_args['validate_generation'] = generation_request
        
        if self.validation_delay > 0:
            await asyncio.sleep(self.validation_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Check for predefined result
        gen_key = str(generation_request.request_id)
        if gen_key in self.generation_results:
            return self.generation_results[gen_key]
        
        # Default result
        return GuardResult(
            is_allowed=self.default_allow,
            reason="Mock guard validation passed" if self.default_allow else "Mock guard validation rejected",
            risk_score=0.1 if self.default_allow else 0.9,
            metadata={"mock": True}
        )
    
    def set_query_result(self, query_id: str, result: GuardResult):
        """Set predefined result for query validation"""
        self.query_results[query_id] = result
    
    def set_generation_result(self, request_id: str, result: GuardResult):
        """Set predefined result for generation validation"""
        self.generation_results[request_id] = result
    
    def set_validation_delay(self, delay: float):
        """Set delay for validation operations"""
        self.validation_delay = delay
    
    def set_failure(self, should_fail: bool, message: str = "Mock guard validation failed"):
        """Set whether to simulate failure"""
        self.should_fail = should_fail
        self.failure_message = message
    
    def reset(self):
        """Reset mock state"""
        self.call_count = 0
        self.last_call_args.clear()
        self.validation_delay = 0.0
        self.should_fail = False
        self.query_results.clear()
        self.generation_results.clear()
