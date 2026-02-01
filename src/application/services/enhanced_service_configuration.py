"""Enhanced Service Configuration with Safety Services"""

from typing import Dict, Any, List
import logging

from ..services.dependency_injection import DIContainer, ServiceConfiguration
from ...domain.services.retrieval_service import RetrievalService, RetrievalConfig
from ...domain.services.reranking_service import HybridReranker, RerankingConfig
from ...domain.services.guard_service import SecurityGuard, RateLimitGuard, CompositeGuard, GuardConfig
from ...domain.services.llama_guard_service import LlamaGuardService, LlamaGuardConfig
from ...domain.services.hallucination_detector import HallucinationDetector, HallucinationDetectionConfig
from ...domain.services.enhanced_safety_guard import EnhancedSafetyGuard, FallbackConfig, SafetyTier
from ...domain.services.safety_metrics_service import SafetyMetricsService, SafetyMetricsConfig
from ...infrastructure.repositories.postgres_document_repository import PostgresDocumentRepository, PostgresChunkRepository
from ...infrastructure.repositories.chroma_vector_repository import ChromaVectorRepository
from ...infrastructure.services.sentence_transformer_provider import SentenceTransformerProvider
from ...infrastructure.tracing.phoenix_tracer import TracingService, create_tracer
from ...infrastructure.database.connection import create_database_connection
from ...infrastructure.config.settings import get_config
from ..use_cases.query_use_case import QueryUseCase
from ..use_cases.document_use_case import DocumentUseCase, DocumentProcessingConfig


logger = logging.getLogger(__name__)


class EnhancedRAGServiceConfiguration(ServiceConfiguration):
    """Enhanced RAG system service configuration with comprehensive safety"""
    
    def configure_services(self) -> DIContainer:
        """Configure all RAG system services with safety enhancements"""
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
        
        # Safety services (new)
        self._configure_safety_services(container)
        
        # Domain services
        self._configure_domain_services(container)
        
        # Application services
        self._configure_application_services(container)
        
        logger.info("Enhanced RAG system services with safety configured")
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
    
    def _configure_safety_services(self, container: DIContainer):
        """Configure safety and security services"""
        # Llama Guard service
        container.register_singleton(
            LlamaGuardService,
            factory=self._create_llama_guard_service
        )
        
        # Hallucination detector
        container.register_singleton(
            HallucinationDetector,
            factory=self._create_hallucination_detector
        )
        
        # Enhanced safety guard
        container.register_singleton(
            EnhancedSafetyGuard,
            factory=self._create_enhanced_safety_guard
        )
        
        # Safety metrics service
        container.register_singleton(
            SafetyMetricsService,
            factory=self._create_safety_metrics_service
        )
        
        # Legacy guards (for backward compatibility)
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
    
    def _configure_domain_services(self, container: DIContainer):
        """Configure domain services"""
        # Reranker
        container.register_singleton(
            HybridReranker,
            factory=self._create_reranker
        )
        
        # Retrieval service
        container.register_scoped(
            RetrievalService,
            factory=self._create_retrieval_service
        )
    
    def _configure_application_services(self, container: DIContainer):
        """Configure application services"""
        # Query use case (enhanced with safety)
        container.register_scoped(
            QueryUseCase,
            factory=self._create_enhanced_query_use_case
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
    
    # Safety service factories
    async def _create_llama_guard_service(self):
        """Create Llama Guard service"""
        config = await get_config()
        llama_guard_config = LlamaGuardConfig(
            model_name="meta-llama/LlamaGuard-7b",
            enable_input_filtering=config.security.enable_content_filter,
            enable_output_filtering=True,
            enable_context_analysis=True,
            fallback_on_failure=True
        )
        return LlamaGuardService(llama_guard_config)
    
    async def _create_hallucination_detector(self):
        """Create hallucination detector"""
        config = await get_config()
        hallucination_config = HallucinationDetectionConfig(
            embedding_model=config.model.embedding_model,
            similarity_threshold=0.3,
            factual_consistency_threshold=0.5,
            enable_semantic_analysis=True,
            enable_factual_verification=True
        )
        return HallucinationDetector(hallucination_config)
    
    async def _create_enhanced_safety_guard(self):
        """Create enhanced safety guard"""
        llama_guard = await container.resolve(LlamaGuardService)
        hallucination_detector = await container.resolve(HallucinationDetector)
        
        fallback_config = FallbackConfig(
            default_strategy=FallbackStrategy.REJECT,
            enable_circuit_breaker=True,
            safety_tier=SafetyTier.MODERATE,
            human_review_threshold=0.8
        )
        
        return EnhancedSafetyGuard(
            llama_guard_config=llama_guard.config,
            hallucination_config=hallucination_detector.config,
            fallback_config=fallback_config
        )
    
    async def _create_safety_metrics_service(self):
        """Create safety metrics service"""
        config = SafetyMetricsConfig(
            enable_real_time_metrics=True,
            enable_anomaly_detection=True,
            enable_trend_analysis=True,
            alert_thresholds={
                "high_risk_requests_per_minute": 10,
                "hallucination_rate": 0.2,
                "safety_failure_rate": 0.05
            }
        )
        return SafetyMetricsService(config)
    
    async def _create_reranker(self):
        """Create reranker"""
        config = await get_config()
        reranking_config = RerankingConfig()
        return HybridReranker(reranking_config)
    
    async def _create_security_guard(self):
        """Create legacy security guard"""
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
    
    async def _create_enhanced_query_use_case(self):
        """Create enhanced query use case with safety"""
        retrieval_service = await container.resolve(RetrievalService)
        enhanced_safety_guard = await container.resolve(EnhancedSafetyGuard)
        safety_metrics = await container.resolve(SafetyMetricsService)
        vector_repository = await container.resolve(ChromaVectorRepository)
        
        # Create enhanced query use case with safety integration
        return EnhancedQueryUseCase(
            retrieval_service=retrieval_service,
            safety_guard=enhanced_safety_guard,
            safety_metrics=safety_metrics,
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


class EnhancedQueryUseCase:
    """Enhanced query use case with integrated safety"""
    
    def __init__(
        self,
        retrieval_service,
        safety_guard,
        safety_metrics,
        vector_search_repo,
        generation_service=None
    ):
        self.retrieval_service = retrieval_service
        self.safety_guard = safety_guard
        self.safety_metrics = safety_metrics
        self.vector_search_repo = vector_search_repo
        self.generation_service = generation_service
    
    async def execute_query(self, query_request):
        """Execute query with comprehensive safety checks"""
        start_time = datetime.now()
        
        try:
            # Step 1: Enhanced safety validation
            safety_decision = await self.safety_guard.validate_query(query_request)
            
            # Record safety metrics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.safety_metrics.record_safety_decision(safety_decision, processing_time)
            
            if not safety_decision.allowed:
                logger.warning(f"Query rejected by safety guard: {safety_decision.primary_reason}")
                return {
                    "query_id": query_request.query_id,
                    "results": [],
                    "processing_time_ms": int(processing_time),
                    "safety_decision": safety_decision,
                    "metadata": {"rejected": True, "reason": safety_decision.primary_reason}
                }
            
            # Step 2: Process query through retrieval service
            results = await self.retrieval_service.process_query(query_request)
            
            # Step 3: Return enhanced response
            return {
                "query_id": query_request.query_id,
                "results": results,
                "processing_time_ms": int(processing_time),
                "safety_decision": safety_decision,
                "metadata": {
                    "result_count": len(results),
                    "query_type": query_request.query_type.value,
                    "top_k": query_request.top_k,
                    "safety_validated": True
                }
            }
            
        except Exception as e:
            logger.error(f"Enhanced query execution failed: {e}")
            raise
    
    async def execute_generation(self, generation_request):
        """Execute generation with comprehensive safety checks"""
        start_time = datetime.now()
        
        try:
            # Step 1: Enhanced safety validation for input
            input_safety_decision = await self.safety_guard.validate_query(
                QueryRequest(
                    query=generation_request.query,
                    query_id=generation_request.request_id,
                    metadata=generation_request.metadata
                )
            )
            
            if not input_safety_decision.allowed:
                return {
                    "request_id": generation_request.request_id,
                    "response": "",
                    "model_name": generation_request.model_name,
                    "tokens_used": 0,
                    "processing_time_ms": 0,
                    "safety_decision": input_safety_decision,
                    "metadata": {"rejected": True, "reason": input_safety_decision.primary_reason}
                }
            
            # Step 2: Generate response
            if self.generation_service:
                generation_response = await self.generation_service.generate(generation_request)
            else:
                # Fallback response
                generation_response = {
                    "response": self._generate_fallback_response(generation_request),
                    "tokens_used": 100,
                    "model_name": generation_request.model_name
                }
            
            # Step 3: Validate generated response
            output_safety_decision = await self.safety_guard.validate_generation(
                generation_request, generation_response["response"]
            )
            
            # Step 4: Check for hallucinations if context is available
            hallucination_result = None
            if generation_request.context and hasattr(self.safety_guard, 'hallucination_detector'):
                hallucination_result = await self.safety_guard.hallucination_detector.detect_hallucination(
                    generation_request.query,
                    generation_response["response"],
                    generation_request.context
                )
                self.safety_metrics.record_hallucination_detection(hallucination_result)
            
            # Record metrics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.safety_metrics.record_safety_decision(output_safety_decision, processing_time)
            
            # Step 5: Return response with safety information
            return {
                "request_id": generation_request.request_id,
                "response": generation_response["response"] if output_safety_decision.allowed else "",
                "model_name": generation_response["model_name"],
                "tokens_used": generation_response["tokens_used"],
                "processing_time_ms": int(processing_time),
                "safety_decision": output_safety_decision,
                "hallucination_result": hallucination_result,
                "metadata": {
                    "context_length": len(generation_request.context),
                    "max_tokens": generation_request.max_tokens,
                    "temperature": generation_request.temperature,
                    "safety_validated": True
                }
            }
            
        except Exception as e:
            logger.error(f"Enhanced generation execution failed: {e}")
            raise
    
    def _generate_fallback_response(self, generation_request):
        """Generate fallback response"""
        context_text = " ".join([result.text for result in generation_request.context])
        
        if not context_text:
            return "I don't have enough information to answer your question."
        
        return f"Based on the available information: {context_text[:500]}..."


# Import container for factory functions
from ..services.dependency_injection import get_container
from datetime import datetime
from ...domain.entities.query import QueryRequest
