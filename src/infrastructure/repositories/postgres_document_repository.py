"""PostgreSQL implementation of document repository"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.entities.document import Document, TextChunk, DocumentMetadata, ProcessingStatus, DocumentType
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository
from ...infrastructure.config.settings import get_config
from ...infrastructure.database.models import DocumentDB, ChunkDB


logger = logging.getLogger(__name__)


class PostgresDocumentRepository(DocumentRepository):
    """PostgreSQL implementation of DocumentRepository"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, document: Document) -> Document:
        """Save a document"""
        try:
            # Check if document exists
            stmt = select(DocumentDB).where(DocumentDB.document_id == str(document.document_id))
            result = await self.session.execute(stmt)
            existing_doc = result.scalar_one_or_none()
            
            if existing_doc:
                # Update existing document
                existing_doc.filename = document.metadata.filename
                existing_doc.file_type = document.metadata.file_type.value
                existing_doc.size_bytes = document.metadata.size_bytes
                existing_doc.status = document.metadata.status.value
                existing_doc.updated_at = datetime.utcnow()
                existing_doc.metadata = document.metadata.metadata
                db_doc = existing_doc
            else:
                # Create new document
                db_doc = DocumentDB(
                    document_id=str(document.document_id),
                    filename=document.metadata.filename,
                    file_type=document.metadata.file_type.value,
                    size_bytes=document.metadata.size_bytes,
                    status=document.metadata.status.value,
                    created_at=document.metadata.created_at,
                    updated_at=document.metadata.updated_at,
                    metadata=document.metadata.metadata
                )
                self.session.add(db_doc)
            
            await self.session.commit()
            await self.session.refresh(db_doc)
            
            # Convert back to domain entity
            return self._map_to_domain(db_doc)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to save document: {e}")
            raise DocumentRepositoryError(f"Failed to save document: {str(e)}")
    
    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        """Find document by ID"""
        try:
            stmt = select(DocumentDB).where(DocumentDB.document_id == str(document_id))
            result = await self.session.execute(stmt)
            db_doc = result.scalar_one_or_none()
            
            if db_doc:
                return self._map_to_domain(db_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to find document by ID: {e}")
            raise DocumentRepositoryError(f"Failed to find document: {str(e)}")
    
    async def find_by_filename(self, filename: str) -> Optional[Document]:
        """Find document by filename"""
        try:
            stmt = select(DocumentDB).where(DocumentDB.filename == filename)
            result = await self.session.execute(stmt)
            db_doc = result.scalar_one_or_none()
            
            if db_doc:
                return self._map_to_domain(db_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to find document by filename: {e}")
            raise DocumentRepositoryError(f"Failed to find document: {str(e)}")
    
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        """Find all documents with pagination"""
        try:
            stmt = select(DocumentDB).offset(skip).limit(limit).order_by(DocumentDB.created_at.desc())
            result = await self.session.execute(stmt)
            db_docs = result.scalars().all()
            
            return [self._map_to_domain(db_doc) for db_doc in db_docs]
            
        except Exception as e:
            logger.error(f"Failed to find all documents: {e}")
            raise DocumentRepositoryError(f"Failed to find documents: {str(e)}")
    
    async def find_by_status(self, status: ProcessingStatus) -> List[Document]:
        """Find documents by processing status"""
        try:
            stmt = select(DocumentDB).where(DocumentDB.status == status.value).order_by(DocumentDB.created_at.desc())
            result = await self.session.execute(stmt)
            db_docs = result.scalars().all()
            
            return [self._map_to_domain(db_doc) for db_doc in db_docs]
            
        except Exception as e:
            logger.error(f"Failed to find documents by status: {e}")
            raise DocumentRepositoryError(f"Failed to find documents: {str(e)}")
    
    async def delete(self, document_id: UUID) -> bool:
        """Delete a document"""
        try:
            stmt = delete(DocumentDB).where(DocumentDB.document_id == str(document_id))
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete document: {e}")
            raise DocumentRepositoryError(f"Failed to delete document: {str(e)}")
    
    async def update_status(self, document_id: UUID, status: ProcessingStatus) -> bool:
        """Update document status"""
        try:
            stmt = (
                update(DocumentDB)
                .where(DocumentDB.document_id == str(document_id))
                .values(
                    status=status.value,
                    updated_at=datetime.utcnow()
                )
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update document status: {e}")
            raise DocumentRepositoryError(f"Failed to update status: {str(e)}")
    
    async def get_document_count(self) -> int:
        """Get total document count"""
        try:
            from sqlalchemy import func
            stmt = select(func.count(DocumentDB.document_id))
            result = await self.session.execute(stmt)
            return result.scalar()
            
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            raise DocumentRepositoryError(f"Failed to get count: {str(e)}")
    
    def _map_to_domain(self, db_doc: DocumentDB) -> Document:
        """Map database model to domain entity"""
        metadata = DocumentMetadata(
            filename=db_doc.filename,
            file_type=DocumentType(db_doc.file_type),
            size_bytes=db_doc.size_bytes,
            created_at=db_doc.created_at,
            updated_at=db_doc.updated_at,
            status=ProcessingStatus(db_doc.status),
            metadata=db_doc.metadata or {}
        )
        
        return Document(
            document_id=UUID(db_doc.document_id),
            metadata=metadata,
            chunks=[]  # Chunks would be loaded separately
        )


class PostgresChunkRepository(ChunkRepository):
    """PostgreSQL implementation of ChunkRepository"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, chunk: TextChunk) -> TextChunk:
        """Save a text chunk"""
        try:
            # Check if chunk exists
            stmt = select(ChunkDB).where(ChunkDB.chunk_id == str(chunk.chunk_id))
            result = await self.session.execute(stmt)
            existing_chunk = result.scalar_one_or_none()
            
            if existing_chunk:
                # Update existing chunk
                existing_chunk.text = chunk.text
                existing_chunk.chunk_index = chunk.chunk_index
                existing_chunk.start_char = chunk.start_char
                existing_chunk.end_char = chunk.end_char
                existing_chunk.metadata = chunk.metadata
                db_chunk = existing_chunk
            else:
                # Create new chunk
                db_chunk = ChunkDB(
                    chunk_id=str(chunk.chunk_id),
                    document_id=str(chunk.document_id),
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    metadata=chunk.metadata
                )
                self.session.add(db_chunk)
            
            await self.session.commit()
            await self.session.refresh(db_chunk)
            
            return self._map_to_domain(db_chunk)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to save chunk: {e}")
            raise DocumentRepositoryError(f"Failed to save chunk: {str(e)}")
    
    async def find_by_id(self, chunk_id: UUID) -> Optional[TextChunk]:
        """Find chunk by ID"""
        try:
            stmt = select(ChunkDB).where(ChunkDB.chunk_id == str(chunk_id))
            result = await self.session.execute(stmt)
            db_chunk = result.scalar_one_or_none()
            
            if db_chunk:
                return self._map_to_domain(db_chunk)
            return None
            
        except Exception as e:
            logger.error(f"Failed to find chunk by ID: {e}")
            raise DocumentRepositoryError(f"Failed to find chunk: {str(e)}")
    
    async def find_by_document_id(self, document_id: UUID) -> List[TextChunk]:
        """Find all chunks for a document"""
        try:
            stmt = (
                select(ChunkDB)
                .where(ChunkDB.document_id == str(document_id))
                .order_by(ChunkDB.chunk_index)
            )
            result = await self.session.execute(stmt)
            db_chunks = result.scalars().all()
            
            return [self._map_to_domain(db_chunk) for db_chunk in db_chunks]
            
        except Exception as e:
            logger.error(f"Failed to find chunks by document ID: {e}")
            raise DocumentRepositoryError(f"Failed to find chunks: {str(e)}")
    
    async def delete_by_document_id(self, document_id: UUID) -> bool:
        """Delete all chunks for a document"""
        try:
            stmt = delete(ChunkDB).where(ChunkDB.document_id == str(document_id))
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete chunks: {e}")
            raise DocumentRepositoryError(f"Failed to delete chunks: {str(e)}")
    
    async def search_text(self, query: str, limit: int = 10) -> List[TextChunk]:
        """Search chunks by text content"""
        try:
            stmt = (
                select(ChunkDB)
                .where(ChunkDB.text.ilike(f"%{query}%"))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            db_chunks = result.scalars().all()
            
            return [self._map_to_domain(db_chunk) for db_chunk in db_chunks]
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            raise DocumentRepositoryError(f"Failed to search chunks: {str(e)}")
    
    def _map_to_domain(self, db_chunk: ChunkDB) -> TextChunk:
        """Map database model to domain entity"""
        return TextChunk(
            chunk_id=UUID(db_chunk.chunk_id),
            document_id=UUID(db_chunk.document_id),
            text=db_chunk.text,
            chunk_index=db_chunk.chunk_index,
            start_char=db_chunk.start_char,
            end_char=db_chunk.end_char,
            metadata=db_chunk.metadata or {}
        )


class DocumentRepositoryError(Exception):
    """Document repository errors"""
    pass
