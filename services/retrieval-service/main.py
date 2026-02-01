from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import httpx
import logging
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import json

from shared.models.base import (
    QueryRequest, RetrievalResult, QueryType, BaseResponse,
    ErrorResponse, GenerationRequest
)
from shared.config.settings import settings
from shared.utils.database import get_db, get_redis, get_clickhouse
from sqlalchemy.orm import Session
from .rag_pipeline import RAGPipeline, RAGConfig

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Retrieval Service starting up...")
    # Initialize service clients
    app.state.embedding_client = httpx.AsyncClient(timeout=30.0)
    app.state.vector_client = httpx.AsyncClient(timeout=30.0)
    
    # Initialize RAG pipeline
    rag_config = RAGConfig(
        retrieval_top_k=getattr(settings, 'rag_retrieval_top_k', 20),
        min_similarity_score=getattr(settings, 'rag_min_similarity_score', 0.5),
        use_reranking=getattr(settings, 'rag_use_reranking', True),
        use_diversity_rerank=getattr(settings, 'rag_use_diversity_rerank', True)
    )
    app.state.rag_pipeline = RAGPipeline(
        app.state.embedding_client,
        app.state.vector_client,
        rag_config
    )
    
    yield
    logger.info("Retrieval Service shutting down...")
    await app.state.embedding_client.aclose()
    await app.state.vector_client.aclose()

app = FastAPI(
    title="Retrieval Service",
    description="Query processing and document retrieval orchestration service",
    version="1.0.0",
    lifespan=lifespan
)


class RetrievalEngine:
    """Main retrieval orchestration engine."""
    
    def __init__(self, embedding_client: httpx.AsyncClient, vector_client: httpx.AsyncClient):
        self.embedding_client = embedding_client
        self.vector_client = vector_client
        self.embedding_service_url = "http://embedding-service:8002"
        self.vector_service_url = "http://vector-service:8003"
    
    async def process_query(self, query_request: QueryRequest) -> List[RetrievalResult]:
        """Process a query and retrieve relevant documents."""
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Generate query embedding
            query_embedding = await self._generate_query_embedding(
                query_request.query, 
                query_request.metadata.get("model_name")
            )
            
            # Step 2: Search vector store
            search_results = await self._search_vectors(
                query_embedding, 
                query_request.top_k,
                query_request.filters
            )
            
            # Step 3: Apply re-ranking if needed
            if query_request.query_type == QueryType.HYBRID:
                search_results = await self._hybrid_rerank(
                    query_request.query, 
                    search_results
                )
            
            # Step 4: Apply filters
            filtered_results = await self._apply_filters(
                search_results, 
                query_request.filters
            )
            
            # Step 5: Log metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._log_query_metrics(query_request, filtered_results, processing_time)
            
            return filtered_results[:query_request.top_k]
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")
    
    async def _generate_query_embedding(self, query: str, model_name: Optional[str] = None) -> List[float]:
        """Generate embedding for the query."""
        try:
            params = {
                "chunk_id": f"query_{datetime.utcnow().timestamp()}",
                "text": query
            }
            if model_name:
                params["model_name"] = model_name
                
            response = await self.embedding_client.post(
                f"{self.embedding_service_url}/embeddings/generate",
                params=params
            )
            response.raise_for_status()
            
            embedding_data = response.json()
            return embedding_data["embedding"]
            
        except httpx.HTTPError as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=503, detail="Embedding service unavailable")
    
    async def _search_vectors(self, query_embedding: List[float], top_k: int, filters: Dict[str, Any]) -> List[RetrievalResult]:
        """Search for similar vectors."""
        try:
            response = await self.vector_client.post(
                f"{self.vector_service_url}/vectors/search",
                json={
                    "query_embedding": query_embedding,
                    "top_k": top_k * 2  # Get more results for re-ranking
                }
            )
            response.raise_for_status()
            
            search_results = response.json()
            return [RetrievalResult(**result) for result in search_results]
            
        except httpx.HTTPError as e:
            logger.error(f"Vector search failed: {e}")
            raise HTTPException(status_code=503, detail="Vector service unavailable")
    
    async def _hybrid_rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Apply hybrid re-ranking based on multiple factors."""
        try:
            # Simple re-ranking based on text similarity and original score
            # In production, would use more sophisticated re-ranking models
            
            reranked_results = []
            for result in results:
                # Calculate text similarity (simplified)
                text_similarity = self._calculate_text_similarity(query, result.text)
                
                # Combine scores (weighted average)
                combined_score = 0.7 * result.score + 0.3 * text_similarity
                
                # Update result score
                result.score = combined_score
                reranked_results.append(result)
            
            # Sort by combined score
            reranked_results.sort(key=lambda x: x.score, reverse=True)
            return reranked_results
            
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            # Return original results if re-ranking fails
            return results
    
    def _calculate_text_similarity(self, query: str, text: str) -> float:
        """Calculate simple text similarity (Jaccard similarity)."""
        try:
            query_words = set(query.lower().split())
            text_words = set(text.lower().split())
            
            intersection = query_words.intersection(text_words)
            union = query_words.union(text_words)
            
            if not union:
                return 0.0
            
            return len(intersection) / len(union)
            
        except Exception:
            return 0.0
    
    async def _apply_filters(self, results: List[RetrievalResult], filters: Dict[str, Any]) -> List[RetrievalResult]:
        """Apply filters to search results."""
        if not filters:
            return results
        
        filtered_results = []
        
        for result in results:
            # Score filter
            if "min_score" in filters and result.score < filters["min_score"]:
                continue
            
            # Document type filter
            if "document_type" in filters:
                doc_type = result.metadata.get("document_type")
                if doc_type != filters["document_type"]:
                    continue
            
            # Date range filter
            if "date_range" in filters:
                created_at = result.metadata.get("created_at")
                if created_at:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    start_date = filters["date_range"].get("start")
                    end_date = filters["date_range"].get("end")
                    
                    if start_date and created_date < start_date:
                        continue
                    if end_date and created_date > end_date:
                        continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    async def _log_query_metrics(self, query_request: QueryRequest, results: List[RetrievalResult], processing_time_ms: float):
        """Log query metrics to ClickHouse."""
        try:
            clickhouse_client = get_clickhouse()
            
            clickhouse_client.execute(
                "INSERT INTO query_metrics VALUES",
                [{
                    'timestamp': datetime.utcnow(),
                    'query_id': query_request.query_id,
                    'query_text': query_request.query,
                    'processing_time_ms': int(processing_time_ms),
                    'retrieval_count': len(results),
                    'generation_tokens': 0,  # Will be updated by generation service
                    'model_name': query_request.metadata.get("model_name", "default"),
                    'service_name': 'retrieval-service'
                }]
            )
            
        except Exception as e:
            logger.warning(f"Failed to log query metrics: {e}")


class QueryProcessor:
    """Query preprocessing and enhancement."""
    
    @staticmethod
    async def preprocess_query(query: str) -> str:
        """Preprocess query for better retrieval."""
        # Basic preprocessing
        query = query.strip()
        
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Add query expansion (simplified)
        # In production, would use more sophisticated techniques
        expanded_query = query
        
        return expanded_query
    
    @staticmethod
    async def detect_query_type(query: str) -> QueryType:
        """Detect the type of query."""
        query_lower = query.lower()
        
        # Simple heuristic for query type detection
        if any(word in query_lower for word in ['what is', 'define', 'explain']):
            return QueryType.SEMANTIC
        elif any(word in query_lower for word in ['find', 'search', 'look for']):
            return QueryType.HYBRID
        else:
            return QueryType.SEMANTIC


# Database models for query history
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class QueryHistoryDB(Base):
    __tablename__ = "query_history"
    
    query_id = Column(String, primary_key=True)
    query_text = Column(Text, nullable=False)
    query_type = Column(String, nullable=False)
    top_k = Column(Integer, nullable=False)
    filters = Column(JSON)
    results_count = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


@app.post("/query", response_model=List[RetrievalResult])
async def process_query(
    query_request: QueryRequest,
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """Process a query through RAG pipeline."""
    try:
        # Initialize RAG pipeline
        rag_pipeline = app.state.rag_pipeline
        
        # Preprocess query
        query_processor = QueryProcessor()
        processed_query = await query_processor.preprocess_query(query_request.query)
        query_request.query = processed_query
        
        # Detect query type if not specified
        if query_request.query_type == QueryType.SEMANTIC:
            detected_type = await query_processor.detect_query_type(query_request.query)
            query_request.query_type = detected_type
        
        # Process query through RAG pipeline
        start_time = datetime.utcnow()
        results, pipeline_stats = await rag_pipeline.process_query(query_request)
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Save query to database
        query_history = QueryHistoryDB(
            query_id=query_request.query_id,
            query_text=query_request.query,
            query_type=query_request.query_type.value,
            top_k=query_request.top_k,
            filters=query_request.filters,
            results_count=len(results),
            processing_time_ms=int(processing_time),
            created_at=datetime.utcnow()
        )
        db.add(query_history)
        db.commit()
        
        # Cache results in Redis with pipeline stats
        await redis_client.setex(
            f"query:{query_request.query_id}",
            1800,  # 30 minutes
            json.dumps({
                "query_id": query_request.query_id,
                "results": [result.dict() for result in results],
                "pipeline_stats": pipeline_stats,
                "processing_time_ms": int(processing_time)
            })
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/{query_id}", response_model=List[RetrievalResult])
async def get_query_results(
    query_id: str,
    redis_client = Depends(get_redis)
):
    """Get cached query results."""
    try:
        # Try cache first
        cached = await redis_client.get(f"query:{query_id}")
        if cached:
            data = json.loads(cached)
            return [RetrievalResult(**result) for result in data["results"]]
        
        raise HTTPException(status_code=404, detail="Query results not found or expired")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get query results error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queries/history", response_model=List[Dict[str, Any]])
async def get_query_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get query history."""
    try:
        queries = db.query(QueryHistoryDB).order_by(
            QueryHistoryDB.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return [
            {
                "query_id": query.query_id,
                "query_text": query.query_text,
                "query_type": query.query_type,
                "results_count": query.results_count,
                "processing_time_ms": query.processing_time_ms,
                "created_at": query.created_at
            }
            for query in queries
        ]
        
    except Exception as e:
        logger.error(f"Get query history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/suggest")
async def suggest_queries(
    partial_query: str,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Suggest query completions based on history."""
    try:
        # Simple query suggestion based on historical queries
        queries = db.query(QueryHistoryDB).filter(
            QueryHistoryDB.query_text.ilike(f"%{partial_query}%")
        ).order_by(QueryHistoryDB.created_at.desc()).limit(limit).all()
        
        suggestions = []
        for query in queries:
            # Extract relevant part of the query
            if partial_query.lower() in query.query_text.lower():
                suggestions.append({
                    "suggestion": query.query_text,
                    "frequency": 1,  # Would calculate actual frequency
                    "last_used": query.created_at
                })
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Query suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "retrieval-service"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=settings.debug
    )
