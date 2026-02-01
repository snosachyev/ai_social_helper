from sqlalchemy.orm import Session
from ..use_cases.document_use_cases import (
    UploadDocumentUseCase, GetDocumentUseCase, 
    ListDocumentsUseCase, GetDocumentChunksUseCase
)
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository, CacheRepository
from ...infrastructure.repositories.document_repository_impl import (
    SqlAlchemyDocumentRepository, SqlAlchemyChunkRepository, RedisCacheRepository
)
from ...infrastructure.external.document_processor_impl import (
    DocumentTextExtractorImpl, TextChunkerImpl, FileValidatorImpl
)


class DIContainer:
    """Dependency injection container for the application."""
    
    def __init__(self, db_session: Session, redis_client):
        self.db_session = db_session
        self.redis_client = redis_client
    
    def get_document_repository(self) -> DocumentRepository:
        """Get document repository instance."""
        return SqlAlchemyDocumentRepository(self.db_session)
    
    def get_chunk_repository(self) -> ChunkRepository:
        """Get chunk repository instance."""
        return SqlAlchemyChunkRepository(self.db_session)
    
    def get_cache_repository(self) -> CacheRepository:
        """Get cache repository instance."""
        return RedisCacheRepository(self.redis_client)
    
    def get_text_extractor(self):
        """Get text extractor instance."""
        return DocumentTextExtractorImpl()
    
    def get_text_chunker(self):
        """Get text chunker instance."""
        return TextChunkerImpl()
    
    def get_file_validator(self):
        """Get file validator instance."""
        return FileValidatorImpl()
    
    def get_upload_document_use_case(self) -> UploadDocumentUseCase:
        """Get upload document use case instance."""
        return UploadDocumentUseCase(
            document_repo=self.get_document_repository(),
            chunk_repo=self.get_chunk_repository(),
            cache_repo=self.get_cache_repository(),
            text_extractor=self.get_text_extractor(),
            text_chunker=self.get_text_chunker(),
            file_validator=self.get_file_validator()
        )
    
    def get_get_document_use_case(self) -> GetDocumentUseCase:
        """Get get document use case instance."""
        return GetDocumentUseCase(
            document_repo=self.get_document_repository(),
            cache_repo=self.get_cache_repository()
        )
    
    def get_list_documents_use_case(self) -> ListDocumentsUseCase:
        """Get list documents use case instance."""
        return ListDocumentsUseCase(
            document_repo=self.get_document_repository()
        )
    
    def get_get_document_chunks_use_case(self) -> GetDocumentChunksUseCase:
        """Get get document chunks use case instance."""
        return GetDocumentChunksUseCase(
            chunk_repo=self.get_chunk_repository()
        )
