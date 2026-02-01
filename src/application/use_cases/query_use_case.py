"""Query processing use case"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from uuid import UUID

from ...domain.entities.query import QueryRequest, RetrievalResult, GenerationRequest, GenerationResponse
from ...domain.services.retrieval_service import RetrievalService
from ...domain.services.guard_service import Guard, GuardResult
from ...domain.repositories.embedding_repository import VectorSearchRepository


logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Response for query processing"""
    query_id: UUID
    results: List[RetrievalResult]
    processing_time_ms: int
    guard_result: GuardResult
    metadata: Dict[str, Any]


@dataclass
class GenerationResponseData:
    """Response for text generation"""
    request_id: UUID
    response: str
    model_name: str
    tokens_used: int
    processing_time_ms: int
    guard_result: GuardResult
    metadata: Dict[str, Any]


class QueryUseCase:
    """Use case for processing queries"""
    
    def __init__(
        self,
        retrieval_service: RetrievalService,
        guard: Guard,
        vector_search_repo: VectorSearchRepository,
        generation_service: "GenerationService" = None
    ):
        self.retrieval_service = retrieval_service
        self.guard = guard
        self.vector_search_repo = vector_search_repo
        self.generation_service = generation_service
    
    async def execute_query(self, query_request: QueryRequest) -> QueryResponse:
        """Execute a query request"""
        start_time = 0  # Would use actual timestamp
        
        try:
            # Step 1: Guard validation
            guard_result = await self.guard.validate_query(query_request)
            if not guard_result.is_allowed:
                logger.warning(f"Query rejected by guard: {guard_result.reason}")
                return QueryResponse(
                    query_id=query_request.query_id,
                    results=[],
                    processing_time_ms=0,
                    guard_result=guard_result,
                    metadata={"rejected": True, "reason": guard_result.reason}
                )
            
            # Step 2: Process query through retrieval service
            results = await self.retrieval_service.process_query(query_request)
            
            # Step 3: Calculate processing time
            processing_time_ms = 0  # Would calculate actual time
            
            # Step 4: Return response
            return QueryResponse(
                query_id=query_request.query_id,
                results=results,
                processing_time_ms=processing_time_ms,
                guard_result=guard_result,
                metadata={
                    "result_count": len(results),
                    "query_type": query_request.query_type.value,
                    "top_k": query_request.top_k
                }
            )
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise QueryException(f"Query execution failed: {str(e)}")
    
    async def execute_generation(self, generation_request: GenerationRequest) -> GenerationResponseData:
        """Execute a generation request"""
        start_time = 0  # Would use actual timestamp
        
        try:
            # Step 1: Guard validation
            guard_result = await self.guard.validate_generation(generation_request)
            if not guard_result.is_allowed:
                logger.warning(f"Generation rejected by guard: {guard_result.reason}")
                return GenerationResponseData(
                    request_id=generation_request.request_id,
                    response="",
                    model_name=generation_request.model_name,
                    tokens_used=0,
                    processing_time_ms=0,
                    guard_result=guard_result,
                    metadata={"rejected": True, "reason": guard_result.reason}
                )
            
            # Step 2: Generate response (if generation service is available)
            if self.generation_service:
                generation_response = await self.generation_service.generate(generation_request)
            else:
                # Fallback: simple context-based response
                generation_response = GenerationResponse(
                    request_id=generation_request.request_id,
                    response=self._generate_fallback_response(generation_request),
                    model_name=generation_request.model_name,
                    tokens_used=100,  # Estimate
                    processing_time_ms=0
                )
            
            # Step 3: Calculate processing time
            processing_time_ms = 0  # Would calculate actual time
            
            # Step 4: Return response
            return GenerationResponseData(
                request_id=generation_request.request_id,
                response=generation_response.response,
                model_name=generation_response.model_name,
                tokens_used=generation_response.tokens_used,
                processing_time_ms=processing_time_ms,
                guard_result=guard_result,
                metadata={
                    "context_length": len(generation_request.context),
                    "max_tokens": generation_request.max_tokens,
                    "temperature": generation_request.temperature
                }
            )
            
        except Exception as e:
            logger.error(f"Generation execution failed: {e}")
            raise GenerationException(f"Generation execution failed: {str(e)}")
    
    def _generate_fallback_response(self, generation_request: GenerationRequest) -> str:
        """Generate a fallback response when generation service is unavailable"""
        context_text = generation_request.get_context_text()
        
        if not context_text:
            return "I don't have enough information to answer your question."
        
        # Simple fallback: return first few chunks as answer
        max_response_length = 500
        if len(context_text) <= max_response_length:
            return f"Based on the available information: {context_text}"
        else:
            return f"Based on the available information: {context_text[:max_response_length]}..."
    
    async def get_query_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get query suggestions based on partial input"""
        try:
            # This would integrate with a query suggestion service
            # For now, return simple suggestions
            suggestions = [
                f"{partial_query} details",
                f"{partial_query} examples",
                f"what is {partial_query}",
                f"how does {partial_query} work",
                f"{partial_query} benefits"
            ]
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get query suggestions: {e}")
            return []
    
    async def get_query_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get query history for a user"""
        try:
            # This would integrate with query history repository
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to get query history: {e}")
            return []


class QueryException(Exception):
    """Exception for query processing failures"""
    pass


class GenerationException(Exception):
    """Exception for generation failures"""
    pass


# Import GenerationResponse from domain entities
from ...domain.entities.query import GenerationResponse
