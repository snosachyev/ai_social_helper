from typing import List
import pypdf
import docx
from bs4 import BeautifulSoup
import markdown
from pathlib import Path
import logging

from ...domain.services.document_processor import DocumentTextExtractor, TextChunker, FileValidator
from ...domain.entities.document import DocumentType

logger = logging.getLogger(__name__)


class DocumentTextExtractorImpl(DocumentTextExtractor):
    """Implementation of document text extraction."""
    
    async def extract_text(self, file_path: str, file_type: DocumentType) -> str:
        """Extract text from document file."""
        try:
            if file_type == DocumentType.PDF:
                return await self._extract_text_from_pdf(file_path)
            elif file_type == DocumentType.DOCX:
                return await self._extract_text_from_docx(file_path)
            elif file_type == DocumentType.HTML:
                return await self._extract_text_from_html(file_path)
            elif file_type == DocumentType.MD:
                return await self._extract_text_from_markdown(file_path)
            else:  # TXT
                return await self._extract_text_from_txt(file_path)
        except Exception as e:
            logger.error(f"Text extraction error for {file_type}: {e}")
            raise ValueError(f"Failed to extract text from {file_type} file")
    
    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    async def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        doc = docx.Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    async def _extract_text_from_html(self, file_path: str) -> str:
        """Extract text from HTML file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file.read(), 'html.parser')
            return soup.get_text(separator='\n', strip=True)
    
    async def _extract_text_from_markdown(self, file_path: str) -> str:
        """Extract text from Markdown file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
    
    async def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()


class TextChunkerImpl(TextChunker):
    """Implementation of text chunking."""
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into chunks with overlap."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            if end > len(text):
                chunks.append(text[start:])
                break
            
            # Try to break at sentence boundary
            chunk = text[start:end]
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > start + chunk_size // 2:
                chunk = text[start:start + break_point + 1]
                start = start + break_point + 1 - overlap
            else:
                start = end - overlap
            
            chunks.append(chunk.strip())
        
        return [chunk for chunk in chunks if chunk.strip()]


class FileValidatorImpl(FileValidator):
    """Implementation of file validation."""
    
    SUPPORTED_EXTENSIONS = {ext.value for ext in DocumentType}
    
    def validate_file_type(self, filename: str) -> bool:
        """Validate if file type is supported."""
        extension = Path(filename).suffix.lower().lstrip('.')
        return extension in self.SUPPORTED_EXTENSIONS
    
    def get_file_type(self, filename: str) -> DocumentType:
        """Get document type from filename."""
        extension = Path(filename).suffix.lower().lstrip('.')
        
        try:
            return DocumentType(extension)
        except ValueError:
            raise ValueError(f"Unsupported file type: {extension}")
