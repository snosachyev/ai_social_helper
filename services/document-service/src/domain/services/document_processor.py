from abc import ABC, abstractmethod
from typing import List
from ..entities.document import DocumentType


class DocumentTextExtractor(ABC):
    """Abstract interface for text extraction from documents."""
    
    @abstractmethod
    async def extract_text(self, file_path: str, file_type: DocumentType) -> str:
        """Extract text from document file."""
        pass


class TextChunker(ABC):
    """Abstract interface for text chunking."""
    
    @abstractmethod
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into chunks with overlap."""
        pass


class FileValidator(ABC):
    """Abstract interface for file validation."""
    
    @abstractmethod
    def validate_file_type(self, filename: str) -> bool:
        """Validate if file type is supported."""
        pass
    
    @abstractmethod
    def get_file_type(self, filename: str) -> DocumentType:
        """Get document type from filename."""
        pass
