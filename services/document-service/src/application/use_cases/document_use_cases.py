from dataclasses import dataclass
from typing import BinaryIO, Optional
import uuid
import time
import os
import aiofiles
from pathlib import Path

from ...domain.entities.document import Document, TextChunk, ProcessingResult, ProcessingStatus
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository, CacheRepository
from ...domain.services.document_processor import DocumentTextExtractor, TextChunker, FileValidator
from shared.document_contracts.upload import UploadDocumentRequest as SharedUploadDocumentRequest
from shared.document_contracts.upload import UploadDocumentResponse as SharedUploadDocumentResponse
from shared.document_contracts.common import GetDocumentRequest as SharedGetDocumentRequest
from shared.document_contracts.common import GetDocumentResponse as SharedGetDocumentResponse
from shared.document_contracts.common import ListDocumentsRequest as SharedListDocumentsRequest
from shared.document_contracts.common import ListDocumentsResponse as SharedListDocumentsResponse
from shared.document_contracts.chunks import GetDocumentChunksRequest as SharedGetDocumentChunksRequest
from shared.document_contracts.chunks import GetDocumentChunksResponse as SharedGetDocumentChunksResponse
from ..adapters.document_adapter import DocumentAdapter
import logging

logger = logging.getLogger(__name__)


# Internal request/response classes - kept for backward compatibility
# but not exposed externally
@dataclass
class _UploadDocumentRequest:
    """Internal request data for document upload."""
    file: BinaryIO
    filename: str
    content: bytes
    chunk_size: int = 1000
    overlap: int = 200


@dataclass
class _UploadDocumentResponse:
    """Internal response data for document upload."""
    document_id: str
    filename: str
    status: str
    chunk_count: int
    processing_time_ms: int


class UploadDocumentUseCase:
    """Use case for uploading and processing documents."""
    
    def __init__(
        self,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        cache_repo: CacheRepository,
        text_extractor: DocumentTextExtractor,
        text_chunker: TextChunker,
        file_validator: FileValidator,
        upload_dir: str = "./uploads"
    ):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.cache_repo = cache_repo
        self.text_extractor = text_extractor
        self.text_chunker = text_chunker
        self.file_validator = file_validator
        self.upload_dir = upload_dir
    
    async def execute(self, request: SharedUploadDocumentRequest) -> SharedUploadDocumentResponse:
        """Execute document upload and processing."""
        start_time = time.time()
        
        try:
            # Convert shared request to internal request
            internal_request = _UploadDocumentRequest(
                file=request.file,
                filename=request.filename,
                content=request.content,
                chunk_size=request.chunk_size,
                overlap=request.overlap
            )
            
            # Validate file type
            if not self.file_validator.validate_file_type(internal_request.filename):
                raise ValueError(f"Unsupported file type: {internal_request.filename}")
            
            file_type = self.file_validator.get_file_type(internal_request.filename)
            
            # Generate document ID and save file
            document_id = str(uuid.uuid4())
            file_path = os.path.join(self.upload_dir, f"{document_id}_{internal_request.filename}")
            
            # Ensure upload directory exists
            os.makedirs(self.upload_dir, exist_ok=True)
            
            # Save file to disk
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(internal_request.content)
            
            # Create document entity
            document = Document(
                document_id=document_id,
                filename=internal_request.filename,
                file_type=file_type,
                size_bytes=len(internal_request.content),
                status=ProcessingStatus.PROCESSING
            )
            
            # Save document to repository
            document = await self.document_repo.save(document)
            
            # Extract text
            text = await self.text_extractor.extract_text(file_path, file_type)
            
            # Chunk text
            chunk_texts = self.text_chunker.chunk_text(text, internal_request.chunk_size, internal_request.overlap)
            
            # Create chunk entities
            chunks = []
            for i, chunk_text in enumerate(chunk_texts):
                chunk = TextChunk(
                    document_id=document_id,
                    text=chunk_text,
                    chunk_index=i,
                    start_char=0,  # Simplified for now
                    end_char=len(chunk_text)
                )
                chunks.append(chunk)
            
            # Save chunks to repository
            await self.chunk_repo.save_batch(chunks)
            
            # Update document status
            document.update_status(ProcessingStatus.COMPLETED)
            document.add_metadata("chunk_count", len(chunks))
            document = await self.document_repo.update(document)
            
            # Cache document info
            cache_key = f"document:{document_id}"
            cache_data = {
                "document_id": document_id,
                "filename": internal_request.filename,
                "status": document.status.value,
                "chunk_count": len(chunks)
            }
            import json
            await self.cache_repo.set(cache_key, json.dumps(cache_data), 3600)
            
            # Clean up uploaded file
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")
            
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Document {document_id} processed successfully with {len(chunks)} chunks")
            
            return SharedUploadDocumentResponse(
                document_id=document_id,
                filename=internal_request.filename,
                status=document.status.value,
                chunk_count=len(chunks),
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Document upload error: {e}")
            
            # Update document status to failed if document was created
            if 'document' in locals():
                document.update_status(ProcessingStatus.FAILED)
                document.add_metadata("error", str(e))
                await self.document_repo.update(document)
            
            raise e


# Internal request/response classes - kept for backward compatibility
# but not exposed externally
@dataclass
class _GetDocumentRequest:
    """Internal request data for getting document."""
    document_id: str


@dataclass
class _GetDocumentResponse:
    """Internal response data for getting document."""
    document: Optional[Document]


class GetDocumentUseCase:
    """Use case for retrieving document metadata."""
    
    def __init__(
        self,
        document_repo: DocumentRepository,
        cache_repo: CacheRepository
    ):
        self.document_repo = document_repo
        self.cache_repo = cache_repo
    
    async def execute(self, request: SharedGetDocumentRequest) -> SharedGetDocumentResponse:
        """Execute document retrieval."""
        # Convert shared request to internal request
        internal_request = _GetDocumentRequest(document_id=request.document_id)
        
        # Try cache first
        cache_key = f"document:{internal_request.document_id}"
        cached_data = await self.cache_repo.get(cache_key)
        
        if cached_data:
            import json
            from shared.models.base import DocumentMetadata as SharedDocument, DocumentType as SharedDocumentType, ProcessingStatus as SharedProcessingStatus
            data = json.loads(cached_data)
            shared_document = SharedDocument(
                document_id=data["document_id"],
                filename=data["filename"],
                file_type=SharedDocumentType.TXT,  # Default, would need to store in cache
                size_bytes=0,  # Would need to store in cache
                status=SharedProcessingStatus(data["status"])
            )
            return SharedGetDocumentResponse(document=shared_document)
        
        # Query database
        document = await self.document_repo.get_by_id(internal_request.document_id)
        
        if not document:
            return SharedGetDocumentResponse(document=None)
        
        # Cache the result
        cache_data = {
            "document_id": document.document_id,
            "filename": document.filename,
            "status": document.status.value,
            "chunk_count": document.metadata.get("chunk_count", 0)
        }
        import json
        await self.cache_repo.set(cache_key, json.dumps(cache_data), 3600)
        
        # Convert domain document to shared document
        shared_document = DocumentAdapter.domain_to_shared(document)
        return SharedGetDocumentResponse(document=shared_document)


# Internal request/response classes - kept for backward compatibility
# but not exposed externally
@dataclass
class _ListDocumentsRequest:
    """Internal request data for listing documents."""
    skip: int = 0
    limit: int = 100


@dataclass
class _ListDocumentsResponse:
    """Internal response data for listing documents."""
    documents: list[Document]
    total: int


class ListDocumentsUseCase:
    """Use case for listing documents."""
    
    def __init__(self, document_repo: DocumentRepository):
        self.document_repo = document_repo
    
    async def execute(self, request: SharedListDocumentsRequest) -> SharedListDocumentsResponse:
        """Execute document listing."""
        # Convert shared request to internal request
        internal_request = _ListDocumentsRequest(skip=request.skip, limit=request.limit)
        
        documents = await self.document_repo.get_all(internal_request.skip, internal_request.limit)
        
        # Convert domain documents to shared documents
        shared_documents = [DocumentAdapter.domain_to_shared(doc) for doc in documents]
        
        return SharedListDocumentsResponse(
            documents=shared_documents,
            total=len(documents)  # Simplified, would need count query
        )


# Internal request/response classes - kept for backward compatibility
# but not exposed externally
@dataclass
class _GetDocumentChunksRequest:
    """Internal request data for getting document chunks."""
    document_id: str


@dataclass
class _GetDocumentChunksResponse:
    """Internal response data for getting document chunks."""
    chunks: list[TextChunk]


class GetDocumentChunksUseCase:
    """Use case for retrieving document chunks."""
    
    def __init__(self, chunk_repo: ChunkRepository):
        self.chunk_repo = chunk_repo
    
    async def execute(self, request: SharedGetDocumentChunksRequest) -> SharedGetDocumentChunksResponse:
        """Execute document chunks retrieval."""
        # Convert shared request to internal request
        internal_request = _GetDocumentChunksRequest(document_id=request.document_id)
        
        chunks = await self.chunk_repo.get_by_document_id(internal_request.document_id)
        
        return SharedGetDocumentChunksResponse(chunks=chunks)
