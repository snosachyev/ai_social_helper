"""Document repository interface"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..entities.document import Document, TextChunk, DocumentMetadata, ProcessingStatus


class DocumentRepository(ABC):
    """Abstract repository for document operations"""
    
    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Save a document"""
        pass
    
    @abstractmethod
    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        """Find document by ID"""
        pass
    
    @abstractmethod
    async def find_by_filename(self, filename: str) -> Optional[Document]:
        """Find document by filename"""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        """Find all documents with pagination"""
        pass
    
    @abstractmethod
    async def find_by_status(self, status: ProcessingStatus) -> List[Document]:
        """Find documents by processing status"""
        pass
    
    @abstractmethod
    async def delete(self, document_id: UUID) -> bool:
        """Delete a document"""
        pass
    
    @abstractmethod
    async def update_status(self, document_id: UUID, status: ProcessingStatus) -> bool:
        """Update document status"""
        pass
    
    @abstractmethod
    async def get_document_count(self) -> int:
        """Get total document count"""
        pass


class ChunkRepository(ABC):
    """Abstract repository for chunk operations"""
    
    @abstractmethod
    async def save(self, chunk: TextChunk) -> TextChunk:
        """Save a text chunk"""
        pass
    
    @abstractmethod
    async def find_by_id(self, chunk_id: UUID) -> Optional[TextChunk]:
        """Find chunk by ID"""
        pass
    
    @abstractmethod
    async def find_by_document_id(self, document_id: UUID) -> List[TextChunk]:
        """Find all chunks for a document"""
        pass
    
    @abstractmethod
    async def delete_by_document_id(self, document_id: UUID) -> bool:
        """Delete all chunks for a document"""
        pass
    
    @abstractmethod
    async def search_text(self, query: str, limit: int = 10) -> List[TextChunk]:
        """Search chunks by text content"""
        pass
