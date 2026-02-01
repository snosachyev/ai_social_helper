from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List

from ...application.use_cases.document_use_cases import (
    UploadDocumentUseCase, GetDocumentUseCase,
    ListDocumentsUseCase, GetDocumentChunksUseCase,
    UploadDocumentRequest, GetDocumentRequest,
    ListDocumentsRequest, GetDocumentChunksRequest
)
from ...application.services.di_container import DIContainer
from shared.models.base import DocumentMetadata, TextChunk, BaseResponse
from shared.utils.database import get_db, get_redis
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_di_container(
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
) -> DIContainer:
    """Get dependency injection container."""
    return DIContainer(db, redis_client)


@router.post(
    "/documents/upload", 
    response_model=BaseResponse,
    summary="Upload and process a document",
    description="Upload a document file (PDF, DOCX, HTML, Markdown, or TXT) for processing and chunking",
    responses={
        200: {"description": "Document uploaded and processed successfully"},
        400: {"description": "Bad request - unsupported file type or no file provided"},
        500: {"description": "Internal server error"}
    }
)
async def upload_document(
    file: UploadFile = File(
        ..., 
        description="Document file to upload (PDF, DOCX, HTML, MD, or TXT)",
        media_type={
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "text/html": ".html",
            "text/markdown": ".md",
            "text/plain": ".txt"
        }
    ),
    container: DIContainer = Depends(get_di_container)
):
    """Upload and process document."""
    try:
        # Read file content
        content = await file.read()
        
        # Create request
        request = UploadDocumentRequest(
            file=file.file,
            filename=file.filename,
            content=content
        )
        
        # Execute use case
        use_case = container.get_upload_document_use_case()
        response = await use_case.execute(request)
        
        return BaseResponse(
            success=True,
            message=f"Document uploaded and processed successfully. Generated {response.chunk_count} chunks.",
            timestamp=response.processing_time_ms
        )
        
    except ValueError as e:
        logger.error(f"Document upload validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    container: DIContainer = Depends(get_di_container)
):
    """Get document metadata."""
    try:
        # Create request
        request = GetDocumentRequest(document_id=document_id)
        
        # Execute use case
        use_case = container.get_get_document_use_case()
        response = await use_case.execute(request)
        
        if not response.document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Convert to response model
        return DocumentMetadata(
            document_id=response.document.document_id,
            filename=response.document.filename,
            file_type=response.document.file_type,
            size_bytes=response.document.size_bytes,
            created_at=response.document.created_at,
            updated_at=response.document.updated_at,
            status=response.document.status,
            metadata=response.document.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=List[DocumentMetadata])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    container: DIContainer = Depends(get_di_container)
):
    """List documents."""
    try:
        # Create request
        request = ListDocumentsRequest(skip=skip, limit=limit)
        
        # Execute use case
        use_case = container.get_list_documents_use_case()
        response = await use_case.execute(request)
        
        # Convert to response models
        return [
            DocumentMetadata(
                document_id=doc.document_id,
                filename=doc.filename,
                file_type=doc.file_type,
                size_bytes=doc.size_bytes,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                status=doc.status,
                metadata=doc.metadata
            )
            for doc in response.documents
        ]
        
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/chunks", response_model=List[TextChunk])
async def get_document_chunks(
    document_id: str,
    container: DIContainer = Depends(get_di_container)
):
    """Get document chunks."""
    try:
        # Create request
        request = GetDocumentChunksRequest(document_id=document_id)
        
        # Execute use case
        use_case = container.get_get_document_chunks_use_case()
        response = await use_case.execute(request)
        
        if not response.chunks:
            raise HTTPException(status_code=404, detail="Document chunks not found")
        
        # Convert to response models
        return [
            TextChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata=chunk.metadata
            )
            for chunk in response.chunks
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document chunks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "document-service"}
