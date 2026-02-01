"""Retrieval domain service"""

from abc import ABC, abstractmethod
from typing import List, Protocol, runtime_checkable
from dataclasses import dataclass
import logging

from ..entities.query import QueryRequest, QueryType
from ..entities.embedding import EmbeddingVector, RetrievalResult


logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers"""
    
    async def generate_embedding(self, text: str, model_name: str) -> EmbeddingVector:
        """Generate embedding for text"""
        ...
    
    async def generate_batch_embeddings(self, texts: List[str], model_name: str) -> List[EmbeddingVector]:
        """Generate embeddings for multiple texts"""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage and retrieval"""
    
    async def add_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """Add vectors to store"""
        ...
    
    async def search(self, query_embedding: EmbeddingVector, top_k: int, filters: dict = None) -> List[RetrievalResult]:
        """Search for similar vectors"""
        ...
    
    async def delete_vector(self, vector_id: str) -> bool:
        """Delete vector from store"""
        ...


@runtime_checkable
class Reranker(Protocol):
    """Protocol for result reranking"""
    
    async def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank results based on query"""
        ...


@dataclass
class RetrievalConfig:
    """Configuration for retrieval service"""
    default_top_k: int = 5
    max_top_k: int = 100
    enable_hybrid_search: bool = True
    enable_reranking: bool = True
    rerank_threshold: float = 0.5
    min_score_threshold: float = 0.1


class RetrievalService:
    """Core retrieval domain service"""
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        reranker: Reranker = None,
        config: RetrievalConfig = None
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.reranker = reranker
        self.config = config or RetrievalConfig()
    
    async def process_query(self, query_request: QueryRequest) -> List[RetrievalResult]:
        """Process a query and retrieve relevant documents"""
        try:
            # Step 1: Generate query embedding
            query_embedding = await self._generate_query_embedding(query_request)
            
            # Step 2: Search vector store
            search_results = await self._search_vectors(query_request, query_embedding)
            
            # Step 3: Apply reranking if enabled and query is hybrid
            if self.config.enable_reranking and query_request.is_hybrid() and self.reranker:
                search_results = await self.reranker.rerank(query_request.query, search_results)
            
            # Step 4: Apply filters and limits
            filtered_results = self._apply_filters(search_results, query_request)
            
            # Step 5: Return top_k results
            return filtered_results[:query_request.top_k]
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise RetrievalException(f"Query processing failed: {str(e)}")
    
    async def _generate_query_embedding(self, query_request: QueryRequest) -> EmbeddingVector:
        """Generate embedding for the query"""
        model_name = query_request.get_model_name() or "default"
        
        try:
            embedding_vector = await self.embedding_provider.generate_embedding(
                query_request.query, 
                model_name
            )
            return embedding_vector
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingException(f"Failed to generate query embedding: {str(e)}")
    
    async def _search_vectors(self, query_request: QueryRequest, query_embedding: EmbeddingVector) -> List[RetrievalResult]:
        """Search for similar vectors"""
        try:
            # Get more results for reranking if needed
            search_top_k = query_request.top_k * 2 if self.config.enable_reranking else query_request.top_k
            
            results = await self.vector_store.search(
                query_embedding=query_embedding,
                top_k=min(search_top_k, self.config.max_top_k),
                filters=query_request.filters
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise VectorStoreException(f"Vector search failed: {str(e)}")
    
    def _apply_filters(self, results: List[RetrievalResult], query_request: QueryRequest) -> List[RetrievalResult]:
        """Apply filters to search results"""
        filtered_results = []
        
        for result in results:
            # Score filter
            if result.score < self.config.min_score_threshold:
                continue
            
            # Additional filters from query request
            if query_request.has_filter("min_score") and result.score < query_request.filters["min_score"]:
                continue
            
            if query_request.has_filter("document_type"):
                doc_type = result.metadata.get("document_type")
                if doc_type != query_request.filters["document_type"]:
                    continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    async def add_document_embeddings(self, embeddings: List[EmbeddingVector]) -> bool:
        """Add document embeddings to vector store"""
        try:
            success = await self.vector_store.add_vectors(embeddings)
            if not success:
                raise VectorStoreException("Failed to add embeddings to vector store")
            return True
        except Exception as e:
            logger.error(f"Failed to add embeddings: {e}")
            raise VectorStoreException(f"Failed to add embeddings: {str(e)}")


class RetrievalException(Exception):
    """Base exception for retrieval service"""
    pass


class EmbeddingException(RetrievalException):
    """Exception for embedding generation failures"""
    pass


class VectorStoreException(RetrievalException):
    """Exception for vector store failures"""
    pass
