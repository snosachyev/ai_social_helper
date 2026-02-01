"""Query API controller with clean architecture"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any, Optional
import logging
from uuid import UUID

from ...application.use_cases.query_use_case import QueryUseCase, QueryResponse, GenerationResponseData
from ...domain.entities.query import QueryRequest, GenerationRequest, QueryType
from ...domain.entities.embedding import RetrievalResult
from ...application.services.dependency_injection import get_container
from ...infrastructure.tracing.phoenix_tracer import TracingService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


async def get_query_use_case() -> QueryUseCase:
    """Get query use case from DI container"""
    container = get_container()
    return await container.resolve(QueryUseCase)


async def get_tracing_service() -> TracingService:
    """Get tracing service from DI container"""
    container = get_container()
    return await container.resolve(TracingService)


@router.post("/", response_model=Dict[str, Any])
async def process_query(
    query_data: Dict[str, Any],
    query_use_case: QueryUseCase = Depends(get_query_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Process a query and retrieve relevant documents.
    
    Args:
        query_data: Query request data containing:
            - query: str - The query text
            - query_type: str - Type of query (semantic, hybrid, keyword)
            - top_k: int - Number of results to return
            - filters: Dict[str, Any] - Optional filters
            - metadata: Dict[str, Any] - Optional metadata
    
    Returns:
        Query response with results and metadata
    """
    try:
        # Create query request
        query_request = QueryRequest(
            query=query_data.get("query", ""),
            query_type=QueryType(query_data.get("query_type", "semantic")),
            top_k=query_data.get("top_k", 5),
            filters=query_data.get("filters", {}),
            metadata=query_data.get("metadata", {})
        )
        
        # Execute query
        result = await query_use_case.execute_query(query_request)
        
        # Add tracing
        await tracing_service.trace_query(
            query_request=query_request,
            result=result
        )
        
        return {
            "query_id": str(result.query_id),
            "results": [
                {
                    "chunk_id": str(r.chunk_id),
                    "document_id": str(r.document_id),
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata
                }
                for r in result.results
            ],
            "processing_time_ms": result.processing_time_ms,
            "guard_result": {
                "is_allowed": result.guard_result.is_allowed,
                "reason": result.guard_result.reason,
                "risk_score": result.guard_result.risk_score,
                "metadata": result.guard_result.metadata
            },
            "metadata": result.metadata
        }
        
    except ValueError as e:
        logger.warning(f"Invalid query request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@router.post("/generate", response_model=Dict[str, Any])
async def generate_response(
    generation_data: Dict[str, Any],
    query_use_case: QueryUseCase = Depends(get_query_use_case),
    tracing_service: TracingService = Depends(get_tracing_service)
):
    """
    Generate a response based on query and context.
    
    Args:
        generation_data: Generation request data containing:
            - query: str - The query text
            - context: List[Dict] - Context documents
            - model_name: str - Model to use for generation
            - max_tokens: int - Maximum tokens to generate
            - temperature: float - Generation temperature
            - metadata: Dict[str, Any] - Optional metadata
    
    Returns:
        Generated response with metadata
    """
    try:
        # Create generation request
        generation_request = GenerationRequest(
            query=generation_data.get("query", ""),
            context=[
                RetrievalResult(
                    chunk_id=UUID(ctx.get("chunk_id")),
                    document_id=UUID(ctx.get("document_id")),
                    text=ctx.get("text", ""),
                    score=ctx.get("score", 0.0),
                    metadata=ctx.get("metadata", {})
                )
                for ctx in generation_data.get("context", [])
            ],
            model_name=generation_data.get("model_name", "default"),
            max_tokens=generation_data.get("max_tokens", 512),
            temperature=generation_data.get("temperature", 0.7),
            metadata=generation_data.get("metadata", {})
        )
        
        # Generate response with tracing
        async with tracing_service.trace_generation(generation_request):
            response = await query_use_case.execute_generation(generation_request)
        
        # Return response
        return {
            "request_id": str(response.request_id),
            "response": response.response,
            "model_name": response.model_name,
            "tokens_used": response.tokens_used,
            "processing_time_ms": response.processing_time_ms,
            "guard_result": {
                "is_allowed": response.guard_result.is_allowed,
                "reason": response.guard_result.reason,
                "risk_score": response.guard_result.risk_score,
                "metadata": response.guard_result.metadata
            },
            "metadata": response.metadata
        }
        
    except ValueError as e:
        logger.warning(f"Invalid generation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )


@router.get("/suggestions")
async def get_query_suggestions(
    partial_query: str,
    limit: int = 5,
    query_use_case: QueryUseCase = Depends(get_query_use_case)
):
    """
    Get query suggestions based on partial input.
    
    Args:
        partial_query: Partial query text
        limit: Maximum number of suggestions to return
    
    Returns:
        List of query suggestions
    """
    try:
        suggestions = await query_use_case.get_query_suggestions(partial_query, limit)
        
        return {
            "partial_query": partial_query,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Failed to get query suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggestions: {str(e)}"
        )


@router.get("/history")
async def get_query_history(
    user_id: str,
    limit: int = 10,
    query_use_case: QueryUseCase = Depends(get_query_use_case)
):
    """
    Get query history for a user.
    
    Args:
        user_id: User identifier
        limit: Maximum number of historical queries to return
    
    Returns:
        List of historical queries
    """
    try:
        history = await query_use_case.get_query_history(user_id, limit)
        
        return {
            "user_id": user_id,
            "history": history,
            "count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for query service"""
    return {
        "status": "healthy",
        "service": "query-service",
        "version": "1.0.0"
    }


# Import UUID for type hints
from uuid import UUID
from ...domain.entities.embedding import RetrievalResult
