"""Service configuration for dependency injection"""

from typing import Dict, Any, List
import logging

from ..services.dependency_injection import DIContainer, ServiceConfiguration
from ...domain.services.retrieval_service import RetrievalService, RetrievalConfig
from ...domain.services.reranking_service import HybridReranker, RerankingConfig
from ...domain.services.guard_service import SecurityGuard, RateLimitGuard, CompositeGuard, GuardConfig
from ...infrastructure.repositories.postgres_document_repository import PostgresDocumentRepository, PostgresChunkRepository
from ...infrastructure.repositories.chroma_vector_repository import ChromaVectorRepository
from ...infrastructure.services.sentence_transformer_provider import SentenceTransformerProvider
from ...infrastructure.tracing.phoenix_tracer import TracingService, create_tracer
from ...infrastructure.database.connection import create_database_connection
from ...infrastructure.config.settings import get_config
from ..use_cases.query_use_case import QueryUseCase
from ..use_cases.document_use_case import DocumentUseCase, DocumentProcessingConfig


logger = logging.getLogger(__name__)


class RAGServiceConfiguration(ServiceConfiguration):
    """RAG system service configuration"""
    
    def configure_services(self) -> DIContainer:
        """Configure all RAG system services"""
        container = self.container
        
        # Configuration
        container.register_singleton(
            type(await get_config()),
            factory=lambda: get_config()
        )
        
        # Database connections
        container.register_scoped(
            type(create_database_connection()),
            factory=lambda: create_database_connection()
        )
        
        # Repositories
        self._configure_repositories(container)
        
        # Infrastructure services
        self._configure_infrastructure_services(container)
        
        # Domain services
        self._configure_domain_services(container)
        
        # Application services
        self._configure_application_services(container)
        
        logger.info("RAG system services configured")
        return container
    
    def _configure_repositories(self, container: DIContainer):
        """Configure repository services"""
        # Document repository
        container.register_scoped(
            PostgresDocumentRepository,
            factory=self._create_document_repository
        )
        
        # Chunk repository
        container.register_scoped(
            PostgresChunkRepository,
            factory=self._create_chunk_repository
        )
        
        # Vector repository
        container.register_scoped(
            ChromaVectorRepository,
            factory=self._create_vector_repository
        )
    
    def _configure_infrastructure_services(self, container: DIContainer):
        """Configure infrastructure services"""
        # Embedding provider
        container.register_singleton(
            SentenceTransformerProvider,
            factory=self._create_embedding_provider
        )
        
        # Tracing service
        container.register_singleton(
            TracingService,
            factory=self._create_tracing_service
        )
    
    def _configure_domain_services(self, container: DIContainer):
        """Configure domain services"""
        # Reranker
        container.register_singleton(
            HybridReranker,
            factory=self._create_reranker
        )
        
        # Guards
        container.register_singleton(
            SecurityGuard,
            factory=self._create_security_guard
        )
        
        container.register_singleton(
            RateLimitGuard,
            factory=self._create_rate_limit_guard
        )
        
        container.register_singleton(
            CompositeGuard,
            factory=self._create_composite_guard
        )
        
        # Retrieval service
        container.register_scoped(
            RetrievalService,
            factory=self._create_retrieval_service
        )
    
    def _configure_application_services(self, container: DIContainer):
        """Configure application services"""
        # Query use case
        container.register_scoped(
            QueryUseCase,
            factory=self._create_query_use_case
        )
        
        # Document use case
        container.register_scoped(
            DocumentUseCase,
            factory=self._create_document_use_case
        )
    
    async def _create_document_repository(self):
        """Create document repository"""
        db_manager = await container.resolve(type(create_database_connection()))
        async with db_manager.get_session() as session:
            return PostgresDocumentRepository(session)
    
    async def _create_chunk_repository(self):
        """Create chunk repository"""
        db_manager = await container.resolve(type(create_database_connection()))
        async with db_manager.get_session() as session:
            return PostgresChunkRepository(session)
    
    async def _create_vector_repository(self):
        """Create vector repository"""
        return ChromaVectorRepository()
    
    async def _create_embedding_provider(self):
        """Create embedding provider"""
        return SentenceTransformerProvider()
    
    async def _create_tracing_service(self):
        """Create tracing service"""
        config = await get_config()
        tracer = await create_tracer(config.monitoring.dict())
        return TracingService(tracer)
    
    async def _create_reranker(self):
        """Create reranker"""
        config = await get_config()
        reranking_config = RerankingConfig()
        return HybridReranker(reranking_config)
    
    async def _create_security_guard(self):
        """Create security guard"""
        config = await get_config()
        guard_config = GuardConfig(
            max_query_length=1000,
            max_context_length=10000,
            enable_content_filter=config.security.enable_content_filter
        )
        return SecurityGuard(guard_config)
    
    async def _create_rate_limit_guard(self):
        """Create rate limit guard"""
        config = await get_config()
        guard_config = GuardConfig(
            enable_rate_limiting=config.security.enable_rate_limiting,
            rate_limit_per_minute=config.security.rate_limit_per_minute
        )
        return RateLimitGuard(guard_config)
    
    async def _create_composite_guard(self):
        """Create composite guard"""
        security_guard = await container.resolve(SecurityGuard)
        rate_limit_guard = await container.resolve(RateLimitGuard)
        return CompositeGuard([security_guard, rate_limit_guard])
    
    async def _create_retrieval_service(self):
        """Create retrieval service"""
        embedding_provider = await container.resolve(SentenceTransformerProvider)
        vector_repository = await container.resolve(ChromaVectorRepository)
        reranker = await container.resolve(HybridReranker)
        
        config = RetrievalConfig(
            default_top_k=5,
            max_top_k=100,
            enable_hybrid_search=True,
            enable_reranking=True,
            rerank_threshold=0.5,
            min_score_threshold=0.1
        )
        
        return RetrievalService(
            embedding_provider=embedding_provider,
            vector_store=vector_repository,
            reranker=reranker,
            config=config
        )
    
    async def _create_query_use_case(self):
        """Create query use case"""
        retrieval_service = await container.resolve(RetrievalService)
        composite_guard = await container.resolve(CompositeGuard)
        vector_repository = await container.resolve(ChromaVectorRepository)
        
        return QueryUseCase(
            retrieval_service=retrieval_service,
            guard=composite_guard,
            vector_search_repo=vector_repository,
            generation_service=None  # Can be added later
        )
    
    async def _create_document_use_case(self):
        """Create document use case"""
        document_repository = await container.resolve(PostgresDocumentRepository)
        chunk_repository = await container.resolve(PostgresChunkRepository)
        embedding_provider = await container.resolve(SentenceTransformerProvider)
        
        config = DocumentProcessingConfig(
            chunk_size=1000,
            chunk_overlap=200,
            min_chunk_size=50,
            max_chunk_size=2000,
            enable_embedding=True,
            embedding_model="default"
        )
        
        return DocumentUseCase(
            document_repository=document_repository,
            chunk_repository=chunk_repository,
            embedding_provider=embedding_provider,
            config=config
        )


# Import container for factory functions
from ..services.dependency_injection import get_container
