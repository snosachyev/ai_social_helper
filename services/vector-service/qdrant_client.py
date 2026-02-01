"""Qdrant Vector Database Client"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json
from dataclasses import dataclass
import httpx

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition,
    MatchValue, SearchParams, OptimizersConfigDiff
)
from qdrant_client.http.models import CollectionInfo

from shared.models.base import RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class QdrantConfig:
    """Qdrant client configuration."""
    host: str = "localhost"
    port: int = 6333
    timeout: int = 30
    vector_size: int = 768
    distance: str = "Cosine"
    collection_prefix: str = "rag"


class QdrantVectorClient:
    """Production-ready Qdrant vector database client."""
    
    def __init__(self, config: QdrantConfig):
        self.config = config
        self.client: Optional[QdrantClient] = None
        self.collections: Dict[str, str] = {
            "documents": f"{config.collection_prefix}_documents",
            "queries": f"{config.collection_prefix}_queries", 
            "telegram": f"{config.collection_prefix}_telegram"
        }
    
    async def initialize(self):
        """Initialize Qdrant client and create collections."""
        try:
            # Initialize synchronous client
            self.client = QdrantClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout
            )
            
            # Test connection
            self.client.get_collections()
            logger.info("Connected to Qdrant successfully")
            
            # Create collections if they don't exist
            await self._ensure_collections()
            
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise
    
    async def _ensure_collections(self):
        """Ensure all required collections exist."""
        distance_map = {
            "Cosine": Distance.COSINE,
            "Euclidean": Distance.EUCLID,
            "Dot": Distance.DOT
        }
        
        distance = distance_map.get(self.config.distance, Distance.COSINE)
        
        for collection_name in self.collections.values():
            try:
                # Check if collection exists
                self.client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} already exists")
                
            except Exception:
                # Create collection
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.config.vector_size,
                        distance=distance
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        default_segment_number=2,
                        max_segment_size=20000,
                        memmap_threshold=20000
                    )
                )
                logger.info(f"Created collection {collection_name}")
    
    async def insert_vectors(
        self,
        collection_type: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        """Insert vectors into collection."""
        try:
            collection_name = self.collections.get(collection_type)
            if not collection_name:
                raise ValueError(f"Invalid collection type: {collection_type}")
            
            # Convert to PointStruct
            qdrant_points = []
            for point_data in points:
                point = PointStruct(
                    id=point_data["id"],
                    vector=point_data["vector"],
                    payload=point_data.get("payload", {})
                )
                qdrant_points.append(point)
            
            # Insert points
            operation_info = self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points
            )
            
            logger.info(f"Inserted {len(points)} points into {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            return False
    
    async def search_vectors(
        self,
        collection_type: str,
        query_vector: List[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search for similar vectors."""
        try:
            collection_name = self.collections.get(collection_type)
            if not collection_name:
                raise ValueError(f"Invalid collection type: {collection_type}")
            
            # Build filter if provided
            query_filter = None
            if filters:
                query_filter = self._build_filter(filters)
            
            # Search
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,
                search_params=SearchParams(
                    exact=True,
                    hnsw_ef=128
                )
            )
            
            # Convert to RetrievalResult
            results = []
            for scored_point in search_results:
                result = RetrievalResult(
                    id=str(scored_point.id),
                    text=scored_point.payload.get("text", ""),
                    score=float(scored_point.score),
                    metadata=scored_point.payload
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    def _build_filter(self, filters: Dict[str, Any]) -> Filter:
        """Build Qdrant filter from filter dict."""
        conditions = []
        
        for field, value in filters.items():
            if isinstance(value, dict):
                # Handle range filters
                if "gte" in value or "lte" in value:
                    # Would need to implement range conditions
                    pass
                elif "in" in value:
                    conditions.append(
                        FieldCondition(
                            key=field,
                            match=MatchValue(value=value["in"])
                        )
                    )
            else:
                # Simple equality filter
                conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                )
        
        return Filter(must=conditions) if conditions else None
    
    async def delete_vectors(
        self,
        collection_type: str,
        point_ids: List[Union[str, int]]
    ) -> bool:
        """Delete vectors from collection."""
        try:
            collection_name = self.collections.get(collection_type)
            if not collection_name:
                raise ValueError(f"Invalid collection type: {collection_type}")
            
            self.client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            
            logger.info(f"Deleted {len(point_ids)} points from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False
    
    async def get_collection_info(self, collection_type: str) -> Dict[str, Any]:
        """Get collection information."""
        try:
            collection_name = self.collections.get(collection_type)
            if not collection_name:
                raise ValueError(f"Invalid collection type: {collection_type}")
            
            info: CollectionInfo = self.client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "segments_count": info.segments_count,
                "points_count": info.points_count,
                "status": info.status,
                "optimizer_status": info.optimizer_status,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Qdrant health."""
        try:
            if not self.client:
                return {"status": "unhealthy", "error": "Client not initialized"}
            
            # Test connection
            collections = self.client.get_collections()
            
            # Check each collection
            collection_status = {}
            for collection_type, collection_name in self.collections.items():
                try:
                    info = self.client.get_collection(collection_name)
                    collection_status[collection_type] = {
                        "status": "healthy",
                        "vectors_count": info.vectors_count,
                        "points_count": info.points_count
                    }
                except Exception as e:
                    collection_status[collection_type] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            return {
                "status": "healthy",
                "total_collections": len(collections.collections),
                "collections": collection_status
            }
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.client:
            self.client.close()
            logger.info("Qdrant client closed")


class VectorService:
    """High-level vector service for RAG operations."""
    
    def __init__(self, qdrant_client: QdrantVectorClient):
        self.qdrant_client = qdrant_client
    
    async def index_document_chunks(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """Index document chunks."""
        try:
            points = []
            for i, chunk in enumerate(chunks):
                point = {
                    "id": f"{document_id}_{i}",
                    "vector": chunk["embedding"],
                    "payload": {
                        "document_id": document_id,
                        "chunk_id": chunk.get("chunk_id", f"{document_id}_{i}"),
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
                points.append(point)
            
            return await self.qdrant_client.insert_vectors("documents", points)
            
        except Exception as e:
            logger.error(f"Failed to index document chunks: {e}")
            return False
    
    async def search_documents(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search for relevant documents."""
        return await self.qdrant_client.search_vectors(
            "documents",
            query_vector,
            top_k,
            filters=filters
        )
    
    async def index_telegram_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """Index Telegram messages."""
        try:
            points = []
            for message in messages:
                point = {
                    "id": f"telegram_{message['message_id']}",
                    "vector": message["embedding"],
                    "payload": {
                        "message_id": message["message_id"],
                        "channel_id": message["channel_id"],
                        "channel_title": message.get("channel_title", ""),
                        "text": message["text"],
                        "metadata": message.get("metadata", {}),
                        "created_at": message.get("date", datetime.utcnow().isoformat())
                    }
                }
                points.append(point)
            
            return await self.qdrant_client.insert_vectors("telegram", points)
            
        except Exception as e:
            logger.error(f"Failed to index Telegram messages: {e}")
            return False
    
    async def search_telegram_messages(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search for relevant Telegram messages."""
        return await self.qdrant_client.search_vectors(
            "telegram",
            query_vector,
            top_k,
            filters=filters
        )
