"""Embedding repository interface"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..entities.embedding import EmbeddingVector, RetrievalResult


class EmbeddingRepository(ABC):
    """Abstract repository for embedding operations"""
    
    @abstractmethod
    async def save(self, embedding: EmbeddingVector) -> EmbeddingVector:
        """Save an embedding vector"""
        pass
    
    @abstractmethod
    async def save_batch(self, embeddings: List[EmbeddingVector]) -> List[EmbeddingVector]:
        """Save multiple embedding vectors"""
        pass
    
    @abstractmethod
    async def find_by_id(self, vector_id: UUID) -> Optional[EmbeddingVector]:
        """Find embedding by ID"""
        pass
    
    @abstractmethod
    async def find_by_chunk_id(self, chunk_id: UUID) -> Optional[EmbeddingVector]:
        """Find embedding by chunk ID"""
        pass
    
    @abstractmethod
    async def delete(self, vector_id: UUID) -> bool:
        """Delete an embedding"""
        pass
    
    @abstractmethod
    async def delete_by_chunk_id(self, chunk_id: UUID) -> bool:
        """Delete embedding by chunk ID"""
        pass
    
    @abstractmethod
    async def get_embedding_count(self) -> int:
        """Get total embedding count"""
        pass


class VectorSearchRepository(ABC):
    """Abstract repository for vector search operations"""
    
    @abstractmethod
    async def search_similar(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[RetrievalResult]:
        """Search for similar vectors"""
        pass
    
    @abstractmethod
    async def add_vectors(self, embeddings: List[EmbeddingVector]) -> bool:
        """Add vectors to search index"""
        pass
    
    @abstractmethod
    async def update_vector(self, embedding: EmbeddingVector) -> bool:
        """Update vector in search index"""
        pass
    
    @abstractmethod
    async def remove_vector(self, vector_id: UUID) -> bool:
        """Remove vector from search index"""
        pass
    
    @abstractmethod
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get search index statistics"""
        pass
