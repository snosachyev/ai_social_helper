"""Document API controller with clean architecture"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from typing import List, Dict, Any, Optional
import logging
from uuid import UUID

from ...application.use_cases.document_use_case import DocumentUseCase, DocumentUploadResponse
from ...domain.entities.document import DocumentType, ProcessingStatus
from ...application.services.dependency_injection import get_container
from ...infrastructure.tracing.phoenix_tracer import TracingService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


async def get_document_use_case() -> DocumentUseCase:
    """Get document use case from DI container"""
    container = get_container()
    return await container.resolve(DocumentUseCase)


async def get_tracing_service() -> TracingService:
    """Get tracing service from DI container"""
    container = get_container()
    return await container.resolve(TracingService)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_document(
    file: UploadFile = File(...),
    document_use_case: DocumentUseCase = Depends(get_document_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Upload and process a document.
    
    Args:
        file: The document file to upload
    
    Returns:
        Document upload response with metadata
    """
    try:
        # Read file content
        content = await file.read()
        file_content = content.decode('utf-8')
        
        # Determine file type
        file_extension = file.filename.split('.')[-1].lower() if file.filename else 'txt'
        try:
            doc_type = DocumentType(file_extension)
        except ValueError:
            doc_type = DocumentType.TXT
        
        # Process document with tracing
        async with tracing_service.tracer.trace("document.upload") as span_id:
            await tracing_service.tracer.add_attribute(span_id, "document.filename", file.filename)
            await tracing_service.tracer.add_attribute(span_id, "document.size", len(content))
            await tracing_service.tracer.add_attribute(span_id, "document.type", doc_type.value)
            
            response = await document_use_case.upload_document(
                filename=file.filename or "unknown",
                file_content=file_content,
                file_type=doc_type,
                metadata={"original_filename": file.filename}
            )
        
        # Return response
        return {
            "document_id": str(response.document_id),
            "filename": response.filename,
            "status": response.status,
            "chunk_count": response.chunk_count,
            "processing_time_ms": response.processing_time_ms,
            "metadata": response.metadata
        }
        
    except UnicodeDecodeError as e:
        logger.warning(f"File encoding error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding not supported. Please upload UTF-8 encoded text files."
        )
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload failed: {str(e)}"
        )


@router.get("/{document_id}", response_model=Dict[str, Any])
async def get_document(
    document_id: str,
    document_use_case: DocumentUseCase = Depends(get_document_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Get document by ID.
    
    Args:
        document_id: Document UUID
    
    Returns:
        Document details with chunks
    """
    try:
        doc_uuid = UUID(document_id)
        
        # Get document with tracing
        async with tracing_service.tracer.trace("document.get") as span_id:
            await tracing_service.tracer.add_attribute(span_id, "document.id", document_id)
            
            document = await document_use_case.get_document(doc_uuid)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Return response
        return {
            "document_id": str(document.document_id),
            "metadata": {
                "filename": document.metadata.filename,
                "file_type": document.metadata.file_type.value,
                "size_bytes": document.metadata.size_bytes,
                "status": document.metadata.status.value,
                "created_at": document.metadata.created_at.isoformat(),
                "updated_at": document.metadata.updated_at.isoformat(),
                "metadata": document.metadata.metadata
            },
            "chunks": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": chunk.metadata
                }
                for chunk in document.chunks
            ],
            "chunk_count": len(document.chunks)
        }
        
    except ValueError as e:
        logger.warning(f"Invalid document ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.get("/", response_model=Dict[str, Any])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    document_use_case: DocumentUseCase = Depends(get_document_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    List documents with optional filtering.
    
    Args:
        skip: Number of documents to skip (pagination)
        limit: Maximum number of documents to return
        status: Optional status filter
    
    Returns:
        List of documents
    """
    try:
        # Parse status filter
        processing_status = None
        if status:
            try:
                processing_status = ProcessingStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}"
                )
        
        # List documents with tracing
        async with tracing_service.tracer.trace("document.list") as span_id:
            await tracing_service.tracer.add_attribute(span_id, "list.skip", skip)
            await tracing_service.tracer.add_attribute(span_id, "list.limit", limit)
            if processing_status:
                await tracing_service.tracer.add_attribute(span_id, "list.status", status)
            
            documents = await document_use_case.list_documents(skip, limit, processing_status)
        
        # Return response
        return {
            "documents": [
                {
                    "document_id": str(doc.document_id),
                    "filename": doc.metadata.filename,
                    "file_type": doc.metadata.file_type.value,
                    "size_bytes": doc.metadata.size_bytes,
                    "status": doc.metadata.status.value,
                    "created_at": doc.metadata.created_at.isoformat(),
                    "updated_at": doc.metadata.updated_at.isoformat(),
                    "chunk_count": doc.get_chunk_count()
                }
                for doc in documents
            ],
            "count": len(documents),
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.delete("/{document_id}", response_model=Dict[str, Any])
async def delete_document(
    document_id: str,
    document_use_case: DocumentUseCase = Depends(get_document_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Delete a document and all its chunks.
    
    Args:
        document_id: Document UUID
    
    Returns:
        Deletion confirmation
    """
    try:
        doc_uuid = UUID(document_id)
        
        # Delete document with tracing
        async with tracing_service.tracer.trace("document.delete") as span_id:
            await tracing_service.tracer.add_attribute(span_id, "document.id", document_id)
            
            success = await document_use_case.delete_document(doc_uuid)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return {
            "document_id": document_id,
            "deleted": True,
            "message": "Document deleted successfully"
        }
        
    except ValueError as e:
        logger.warning(f"Invalid document ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.patch("/{document_id}/status", response_model=Dict[str, Any])
async def update_document_status(
    document_id: str,
    status_data: Dict[str, str],
    document_use_case: DocumentUseCase = Depends(get_document_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Update document processing status.
    
    Args:
        document_id: Document UUID
        status_data: {"status": "new_status"}
    
    Returns:
        Update confirmation
    """
    try:
        doc_uuid = UUID(document_id)
        new_status = ProcessingStatus(status_data.get("status", "pending"))
        
        # Update status with tracing
        async with tracing_service.tracer.trace("document.update_status") as span_id:
            await tracing_service.tracer.add_attribute(span_id, "document.id", document_id)
            await tracing_service.tracer.add_attribute(span_id, "document.new_status", new_status.value)
            
            success = await document_use_case.update_document_status(doc_uuid, new_status)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return {
            "document_id": document_id,
            "status": new_status.value,
            "updated": True,
            "message": "Document status updated successfully"
        }
        
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update status: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for document service"""
    return {
        "status": "healthy",
        "service": "document-service",
        "version": "1.0.0"
    }
