"""Document chunks contracts."""
from dataclasses import dataclass
from typing import List
from shared.models.base import TextChunk


@dataclass
class GetDocumentChunksRequest:
    """Request data for getting document chunks."""
    document_id: str


@dataclass
class GetDocumentChunksResponse:
    """Response data for getting document chunks."""
    chunks: List[TextChunk]
