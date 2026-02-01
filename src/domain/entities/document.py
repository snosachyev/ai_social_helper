"""Document domain entity"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4


class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    HTML = "html"
    MD = "markdown"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DocumentMetadata:
    """Document metadata value object"""
    filename: str
    file_type: DocumentType
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """Document aggregate root"""
    document_id: UUID = field(default_factory=uuid4)
    metadata: DocumentMetadata = field(default_factory=lambda: DocumentMetadata(filename="", file_type=DocumentType.TXT, size_bytes=0))
    chunks: List["TextChunk"] = field(default_factory=list)
    
    def add_chunk(self, chunk: "TextChunk") -> None:
        """Add a text chunk to the document"""
        if chunk.document_id != self.document_id:
            raise ValueError("Chunk document_id must match document_id")
        self.chunks.append(chunk)
        self.metadata.updated_at = datetime.utcnow()
    
    def update_status(self, status: ProcessingStatus) -> None:
        """Update document processing status"""
        self.metadata.status = status
        self.metadata.updated_at = datetime.utcnow()
    
    def is_processed(self) -> bool:
        """Check if document is fully processed"""
        return self.metadata.status == ProcessingStatus.COMPLETED
    
    def get_chunk_count(self) -> int:
        """Get number of chunks"""
        return len(self.chunks)


@dataclass
class TextChunk:
    """Text chunk entity"""
    chunk_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    text: str = ""
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.text:
            raise ValueError("Text chunk cannot be empty")
        if self.start_char < 0 or self.end_char < self.start_char:
            raise ValueError("Invalid character positions")
    
    def get_text_length(self) -> int:
        """Get text length"""
        return len(self.text)
    
    def overlaps_with(self, other: "TextChunk") -> bool:
        """Check if this chunk overlaps with another"""
        return not (self.end_char <= other.start_char or self.start_char >= other.end_char)
