"""Common document contracts."""
from dataclasses import dataclass
from typing import Optional, List
from shared.models.base import DocumentMetadata as SharedDocument


@dataclass
class GetDocumentRequest:
    """Request data for getting document."""
    document_id: str


@dataclass
class GetDocumentResponse:
    """Response data for getting document."""
    document: Optional[SharedDocument]


@dataclass
class ListDocumentsRequest:
    """Request data for listing documents."""
    skip: int = 0
    limit: int = 100


@dataclass
class ListDocumentsResponse:
    """Response data for listing documents."""
    documents: List[SharedDocument]
    total: int
