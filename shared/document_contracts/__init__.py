"""Shared document contracts for inter-service communication."""
from .upload import UploadDocumentRequest, UploadDocumentResponse
from .common import GetDocumentRequest, GetDocumentResponse, ListDocumentsRequest, ListDocumentsResponse
from .chunks import GetDocumentChunksRequest, GetDocumentChunksResponse

__all__ = [
    'UploadDocumentRequest',
    'UploadDocumentResponse', 
    'GetDocumentRequest',
    'GetDocumentResponse',
    'ListDocumentsRequest',
    'ListDocumentsResponse',
    'GetDocumentChunksRequest',
    'GetDocumentChunksResponse'
]
