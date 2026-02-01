from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.document import Document, TextChunk


class DocumentRepository(ABC):
    """Abstract repository for document persistence."""
    
    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Save document to repository."""
        pass
    
    @abstractmethod
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """Get document by ID."""
        pass
    
    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        """Get all documents with pagination."""
        pass
    
    @abstractmethod
    async def update(self, document: Document) -> Document:
        """Update document in repository."""
        pass
    
    @abstractmethod
    async def delete(self, document_id: str) -> bool:
        """Delete document by ID."""
        pass


class ChunkRepository(ABC):
    """Abstract repository for text chunk persistence."""
    
    @abstractmethod
    async def save(self, chunk: TextChunk) -> TextChunk:
        """Save chunk to repository."""
        pass
    
    @abstractmethod
    async def save_batch(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Save multiple chunks to repository."""
        pass
    
    @abstractmethod
    async def get_by_document_id(self, document_id: str) -> List[TextChunk]:
        """Get all chunks for a document."""
        pass
    
    @abstractmethod
    async def get_by_id(self, chunk_id: str) -> Optional[TextChunk]:
        """Get chunk by ID."""
        pass
    
    @abstractmethod
    async def delete_by_document_id(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        pass


class CacheRepository(ABC):
    """Abstract repository for caching."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass
