from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List
from enum import Enum
import uuid


class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    HTML = "html"
    MD = "md"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document:
    """Domain entity representing a document."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    file_type: DocumentType = DocumentType.TXT
    size_bytes: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, new_status: ProcessingStatus) -> None:
        """Update document status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to document."""
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()


@dataclass
class TextChunk:
    """Domain entity representing a text chunk."""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    text: str = ""
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to chunk."""
        self.metadata[key] = value


@dataclass
class ProcessingResult:
    """Result of document processing."""
    document: Document
    chunks: List[TextChunk]
    processing_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def is_successful(self) -> bool:
        """Check if processing was successful."""
        return len(self.errors) == 0 and self.document.status == ProcessingStatus.COMPLETED
