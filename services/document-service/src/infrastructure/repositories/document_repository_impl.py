from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..database.models import DocumentDB, ChunkDB
from ...domain.entities.document import Document, TextChunk, DocumentType, ProcessingStatus
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository, CacheRepository
import json
import logging

logger = logging.getLogger(__name__)


class SqlAlchemyDocumentRepository(DocumentRepository):
    """SQLAlchemy implementation of DocumentRepository."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def save(self, document: Document) -> Document:
        """Save document to database."""
        doc_db = DocumentDB(
            document_id=document.document_id,
            filename=document.filename,
            file_type=document.file_type.value,
            size_bytes=document.size_bytes,
            status=document.status.value,
            document_metadata=document.metadata,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
        
        self.db.add(doc_db)
        self.db.commit()
        self.db.refresh(doc_db)
        
        logger.info(f"Document {document.document_id} saved to database")
        return document
    
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """Get document by ID."""
        doc_db = self.db.query(DocumentDB).filter(
            DocumentDB.document_id == document_id
        ).first()
        
        if not doc_db:
            return None
        
        return Document(
            document_id=doc_db.document_id,
            filename=doc_db.filename,
            file_type=DocumentType(doc_db.file_type),
            size_bytes=doc_db.size_bytes,
            created_at=doc_db.created_at,
            updated_at=doc_db.updated_at,
            status=ProcessingStatus(doc_db.status),
            metadata=doc_db.document_metadata or {}
        )
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        """Get all documents with pagination."""
        documents_db = self.db.query(DocumentDB).offset(skip).limit(limit).all()
        
        return [
            Document(
                document_id=doc.document_id,
                filename=doc.filename,
                file_type=DocumentType(doc.file_type),
                size_bytes=doc.size_bytes,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                status=ProcessingStatus(doc.status),
                metadata=doc.document_metadata or {}
            )
            for doc in documents_db
        ]
    
    async def update(self, document: Document) -> Document:
        """Update document in database."""
        doc_db = self.db.query(DocumentDB).filter(
            DocumentDB.document_id == document.document_id
        ).first()
        
        if not doc_db:
            raise ValueError(f"Document {document.document_id} not found")
        
        doc_db.status = document.status.value
        doc_db.updated_at = document.updated_at
        doc_db.document_metadata = document.metadata
        
        self.db.commit()
        self.db.refresh(doc_db)
        
        logger.info(f"Document {document.document_id} updated in database")
        return document
    
    async def delete(self, document_id: str) -> bool:
        """Delete document by ID."""
        doc_db = self.db.query(DocumentDB).filter(
            DocumentDB.document_id == document_id
        ).first()
        
        if not doc_db:
            return False
        
        self.db.delete(doc_db)
        self.db.commit()
        
        logger.info(f"Document {document_id} deleted from database")
        return True


class SqlAlchemyChunkRepository(ChunkRepository):
    """SQLAlchemy implementation of ChunkRepository."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def save(self, chunk: TextChunk) -> TextChunk:
        """Save chunk to database."""
        chunk_db = ChunkDB(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            text=chunk.text,
            chunk_index=chunk.chunk_index,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            chunk_metadata=chunk.metadata
        )
        
        self.db.add(chunk_db)
        self.db.commit()
        self.db.refresh(chunk_db)
        
        return chunk
    
    async def save_batch(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Save multiple chunks to database."""
        chunks_db = [
            ChunkDB(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                chunk_metadata=chunk.metadata
            )
            for chunk in chunks
        ]
        
        self.db.add_all(chunks_db)
        self.db.commit()
        
        logger.info(f"Saved {len(chunks)} chunks to database")
        return chunks
    
    async def get_by_document_id(self, document_id: str) -> List[TextChunk]:
        """Get all chunks for a document."""
        chunks_db = self.db.query(ChunkDB).filter(
            ChunkDB.document_id == document_id
        ).order_by(ChunkDB.chunk_index).all()
        
        return [
            TextChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata=chunk.chunk_metadata or {}
            )
            for chunk in chunks_db
        ]
    
    async def get_by_id(self, chunk_id: str) -> Optional[TextChunk]:
        """Get chunk by ID."""
        chunk_db = self.db.query(ChunkDB).filter(
            ChunkDB.chunk_id == chunk_id
        ).first()
        
        if not chunk_db:
            return None
        
        return TextChunk(
            chunk_id=chunk_db.chunk_id,
            document_id=chunk_db.document_id,
            text=chunk_db.text,
            chunk_index=chunk_db.chunk_index,
            start_char=chunk_db.start_char,
            end_char=chunk_db.end_char,
            metadata=chunk_db.chunk_metadata or {}
        )
    
    async def delete_by_document_id(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        chunks_db = self.db.query(ChunkDB).filter(
            ChunkDB.document_id == document_id
        ).all()
        
        if not chunks_db:
            return False
        
        for chunk_db in chunks_db:
            self.db.delete(chunk_db)
        
        self.db.commit()
        
        logger.info(f"Deleted {len(chunks_db)} chunks for document {document_id}")
        return True


class RedisCacheRepository(CacheRepository):
    """Redis implementation of CacheRepository."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            value = self.redis.get(key)
            return value
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        try:
            self.redis.setex(key, ttl_seconds, value)
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            result = self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            result = self.redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
