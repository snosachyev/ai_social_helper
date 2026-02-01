"""Document processing use case"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from uuid import UUID
from datetime import datetime
from pathlib import Path

from ...domain.entities.document import Document, TextChunk, DocumentMetadata, ProcessingStatus, DocumentType
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository
from ...domain.entities.embedding import EmbeddingVector
from ...domain.services.retrieval_service import EmbeddingProvider


logger = logging.getLogger(__name__)


@dataclass
class DocumentUploadResponse:
    """Response for document upload"""
    document_id: UUID
    filename: str
    status: str
    chunk_count: int
    processing_time_ms: int
    metadata: Dict[str, Any]


@dataclass
class DocumentProcessingConfig:
    """Configuration for document processing"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 50
    max_chunk_size: int = 2000
    enable_embedding: bool = True
    embedding_model: str = "default"


class DocumentUseCase:
    """Use case for document processing operations"""
    
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedding_provider: EmbeddingProvider,
        config: DocumentProcessingConfig = None
    ):
        self.document_repository = document_repository
        self.chunk_repository = chunk_repository
        self.embedding_provider = embedding_provider
        self.config = config or DocumentProcessingConfig()
    
    async def upload_document(
        self, 
        filename: str, 
        file_content: str,
        file_type: DocumentType = DocumentType.TXT,
        metadata: Dict[str, Any] = None
    ) -> DocumentUploadResponse:
        """Upload and process a document"""
        start_time = datetime.utcnow()
        
        try:
            # Create document metadata
            document_metadata = DocumentMetadata(
                filename=filename,
                file_type=file_type,
                size_bytes=len(file_content.encode('utf-8')),
                status=ProcessingStatus.PROCESSING,
                metadata=metadata or {}
            )
            
            # Create document entity
            document = Document(
                metadata=document_metadata
            )
            
            # Save document to repository
            document = await self.document_repository.save(document)
            
            # Split document into chunks
            chunks = self._split_text_into_chunks(file_content, document.document_id)
            
            # Save chunks
            for chunk in chunks:
                await self.chunk_repository.save(chunk)
                document.add_chunk(chunk)
            
            # Generate embeddings if enabled
            if self.config.enable_embedding:
                await self._generate_embeddings_for_chunks(chunks)
            
            # Update document status
            document.update_status(ProcessingStatus.COMPLETED)
            await self.document_repository.save(document)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"Document processed: {filename} ({len(chunks)} chunks)")
            
            return DocumentUploadResponse(
                document_id=document.document_id,
                filename=filename,
                status=document.metadata.status.value,
                chunk_count=len(chunks),
                processing_time_ms=int(processing_time),
                metadata={
                    "file_type": file_type.value,
                    "size_bytes": document.metadata.size_bytes
                }
            )
            
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            # Update document status to failed
            if 'document' in locals():
                document.update_status(ProcessingStatus.FAILED)
                await self.document_repository.save(document)
            
            raise DocumentProcessingError(f"Document upload failed: {str(e)}")
    
    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID"""
        try:
            document = await self.document_repository.find_by_id(document_id)
            if document:
                # Load chunks
                chunks = await self.chunk_repository.find_by_document_id(document_id)
                document.chunks = chunks
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise DocumentProcessingError(f"Failed to get document: {str(e)}")
    
    async def list_documents(
        self, 
        skip: int = 0, 
        limit: int = 100,
        status: ProcessingStatus = None
    ) -> List[Document]:
        """List documents with optional status filter"""
        try:
            if status:
                documents = await self.document_repository.find_by_status(status)
            else:
                documents = await self.document_repository.find_all(skip, limit)
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise DocumentProcessingError(f"Failed to list documents: {str(e)}")
    
    async def delete_document(self, document_id: UUID) -> bool:
        """Delete a document and all its chunks"""
        try:
            # Delete chunks first
            await self.chunk_repository.delete_by_document_id(document_id)
            
            # Delete document
            success = await self.document_repository.delete(document_id)
            
            if success:
                logger.info(f"Document deleted: {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise DocumentProcessingError(f"Failed to delete document: {str(e)}")
    
    async def update_document_status(
        self, 
        document_id: UUID, 
        status: ProcessingStatus
    ) -> bool:
        """Update document processing status"""
        try:
            success = await self.document_repository.update_status(document_id, status)
            
            if success:
                logger.info(f"Document status updated: {document_id} -> {status.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update document status: {e}")
            raise DocumentProcessingError(f"Failed to update status: {str(e)}")
    
    def _split_text_into_chunks(self, text: str, document_id: UUID) -> List[TextChunk]:
        """Split text into chunks"""
        chunks = []
        
        # Simple chunking strategy - can be enhanced with more sophisticated methods
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate chunk boundaries
            end = start + self.config.chunk_size
            
            # Adjust for overlap
            if chunk_index > 0:
                start = max(0, start - self.config.chunk_overlap)
            
            # Get chunk text
            chunk_text = text[start:end]
            
            # Skip if too small (except for last chunk)
            if len(chunk_text) < self.config.min_chunk_size and end < len(text):
                start = end
                continue
            
            # Create chunk
            chunk = TextChunk(
                document_id=document_id,
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=start,
                end_char=min(end, len(text)),
                metadata={"chunk_method": "simple"}
            )
            
            chunks.append(chunk)
            
            # Move to next chunk
            start = end
            chunk_index += 1
        
        return chunks
    
    async def _generate_embeddings_for_chunks(self, chunks: List[TextChunk]):
        """Generate embeddings for chunks"""
        try:
            # Prepare texts for batch processing
            texts = [chunk.text for chunk in chunks]
            
            # Generate embeddings
            embeddings = await self.embedding_provider.generate_batch_embeddings(
                texts, 
                self.config.embedding_model
            )
            
            # Associate embeddings with chunks
            for chunk, embedding in zip(chunks, embeddings):
                embedding.chunk_id = chunk.chunk_id
                # In a real implementation, would save to embedding repository
                # await self.embedding_repository.save(embedding)
            
            logger.info(f"Generated embeddings for {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Don't fail the entire document processing if embedding fails
            # Could implement retry logic or fallback strategies


class DocumentProcessingError(Exception):
    """Document processing errors"""
    pass
