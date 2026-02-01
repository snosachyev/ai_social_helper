"""Upload document contracts."""
from dataclasses import dataclass
from typing import BinaryIO
from shared.models.base import ProcessingStatus


@dataclass
class UploadDocumentRequest:
    """Request data for document upload."""
    file: BinaryIO
    filename: str
    content: bytes
    chunk_size: int = 1000
    overlap: int = 200


@dataclass
class UploadDocumentResponse:
    """Response data for document upload."""
    document_id: str
    filename: str
    status: str
    chunk_count: int
    processing_time_ms: int
