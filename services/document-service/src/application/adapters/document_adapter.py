"""Adapter for converting between shared contracts and domain entities."""
from shared.models.base import DocumentMetadata as SharedDocument, DocumentType as SharedDocumentType, ProcessingStatus as SharedProcessingStatus
from src.domain.entities.document import Document as DomainDocument, DocumentType as DomainDocumentType, ProcessingStatus as DomainProcessingStatus
from datetime import datetime


class DocumentAdapter:
    """Adapter for converting between shared and domain document models."""
    
    @staticmethod
    def shared_to_domain(shared_doc: SharedDocument) -> DomainDocument:
        """Convert shared document to domain document."""
        # Convert enums
        domain_file_type = DomainDocumentType(shared_doc.file_type.value)
        domain_status = DomainProcessingStatus(shared_doc.status.value)
        
        return DomainDocument(
            document_id=shared_doc.document_id,
            filename=shared_doc.filename,
            file_type=domain_file_type,
            size_bytes=shared_doc.size_bytes,
            status=domain_status,
            created_at=shared_doc.created_at,
            updated_at=shared_doc.updated_at,
            metadata=shared_doc.metadata
        )
    
    @staticmethod
    def domain_to_shared(domain_doc: DomainDocument) -> SharedDocument:
        """Convert domain document to shared document."""
        # Convert enums
        shared_file_type = SharedDocumentType(domain_doc.file_type.value)
        shared_status = SharedProcessingStatus(domain_doc.status.value)
        
        return SharedDocument(
            document_id=domain_doc.document_id,
            filename=domain_doc.filename,
            file_type=shared_file_type,
            size_bytes=domain_doc.size_bytes,
            created_at=domain_doc.created_at,
            updated_at=domain_doc.updated_at,
            status=shared_status,
            metadata=domain_doc.metadata
        )
