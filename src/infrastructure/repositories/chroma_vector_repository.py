"""ChromaDB implementation of vector repository"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
import json
from datetime import datetime

import chromadb
from chromadb.config import Settings as ChromaSettings

from ...domain.entities.embedding import EmbeddingVector, RetrievalResult
from ...domain.repositories.embedding_repository import EmbeddingRepository, VectorSearchRepository
from ...infrastructure.config.settings import get_config


logger = logging.getLogger(__name__)


class ChromaVectorRepository(EmbeddingRepository, VectorSearchRepository):
    """ChromaDB implementation of vector repositories"""
    
    def __init__(self, collection_name: str = "rag_embeddings"):
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        if self._initialized:
            return
        
        try:
            config = await get_config()
            vector_config = config.vector_store
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=vector_config.chroma_persist_directory)
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": vector_config.metric}
            )
            
            self._initialized = True
            logger.info(f"ChromaDB initialized with collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise VectorRepositoryError(f"Failed to initialize ChromaDB: {str(e)}")
    
    async def save(self, embedding: EmbeddingVector) -> EmbeddingVector:
        """Save an embedding vector"""
        await self.initialize()
        
        try:
            # Add to ChromaDB
            self.collection.add(
                ids=[str(embedding.vector_id)],
                embeddings=[embedding.embedding],
                metadatas=[{
                    "chunk_id": str(embedding.chunk_id),
                    "model_name": embedding.model_name,
                    "dimension": embedding.dimension,
                    "created_at": embedding.created_at.isoformat()
                }]
            )
            
            logger.debug(f"Saved embedding {embedding.vector_id} to ChromaDB")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to save embedding: {e}")
            raise VectorRepositoryError(f"Failed to save embedding: {str(e)}")
    
    async def save_batch(self, embeddings: List[EmbeddingVector]) -> List[EmbeddingVector]:
        """Save multiple embedding vectors"""
        await self.initialize()
        
        try:
            if not embeddings:
                return embeddings
            
            # Prepare batch data
            ids = [str(emb.vector_id) for emb in embeddings]
            embeddings_list = [emb.embedding for emb in embeddings]
            metadatas = [{
                "chunk_id": str(emb.chunk_id),
                "model_name": emb.model_name,
                "dimension": emb.dimension,
                "created_at": emb.created_at.isoformat()
            } for emb in embeddings]
            
            # Add batch to ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                metadatas=metadatas
            )
            
            logger.info(f"Saved {len(embeddings)} embeddings to ChromaDB")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to save batch embeddings: {e}")
            raise VectorRepositoryError(f"Failed to save batch embeddings: {str(e)}")
    
    async def find_by_id(self, vector_id: UUID) -> Optional[EmbeddingVector]:
        """Find embedding by ID"""
        await self.initialize()
        
        try:
            result = self.collection.get(
                ids=[str(vector_id)],
                include=["embeddings", "metadatas"]
            )
            
            if not result["ids"]:
                return None
            
            # Map to domain entity
            embedding_vector = self._map_to_domain(
                result["ids"][0],
                result["embeddings"][0],
                result["metadatas"][0]
            )
            
            return embedding_vector
            
        except Exception as e:
            logger.error(f"Failed to find embedding by ID: {e}")
            raise VectorRepositoryError(f"Failed to find embedding: {str(e)}")
    
    async def find_by_chunk_id(self, chunk_id: UUID) -> Optional[EmbeddingVector]:
        """Find embedding by chunk ID"""
        await self.initialize()
        
        try:
            result = self.collection.get(
                where={"chunk_id": str(chunk_id)},
                include=["embeddings", "metadatas"]
            )
            
            if not result["ids"]:
                return None
            
            # Map to domain entity
            embedding_vector = self._map_to_domain(
                result["ids"][0],
                result["embeddings"][0],
                result["metadatas"][0]
            )
            
            return embedding_vector
            
        except Exception as e:
            logger.error(f"Failed to find embedding by chunk ID: {e}")
            raise VectorRepositoryError(f"Failed to find embedding: {str(e)}")
    
    async def delete(self, vector_id: UUID) -> bool:
        """Delete an embedding"""
        await self.initialize()
        
        try:
            self.collection.delete(ids=[str(vector_id)])
            logger.debug(f"Deleted embedding {vector_id} from ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
            raise VectorRepositoryError(f"Failed to delete embedding: {str(e)}")
    
    async def delete_by_chunk_id(self, chunk_id: UUID) -> bool:
        """Delete embedding by chunk ID"""
        await self.initialize()
        
        try:
            self.collection.delete(where={"chunk_id": str(chunk_id)})
            logger.debug(f"Deleted embedding for chunk {chunk_id} from ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete embedding by chunk ID: {e}")
            raise VectorRepositoryError(f"Failed to delete embedding: {str(e)}")
    
    async def get_embedding_count(self) -> int:
        """Get total embedding count"""
        await self.initialize()
        
        try:
            return self.collection.count()
            
        except Exception as e:
            logger.error(f"Failed to get embedding count: {e}")
            raise VectorRepositoryError(f"Failed to get count: {str(e)}")
    
    async def search_similar(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[RetrievalResult]:
        """Search for similar vectors"""
        await self.initialize()
        
        try:
            # Prepare query arguments
            query_args = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["metadatas", "distances", "documents"]
            }
            
            # Add filters if provided
            if filters:
                where_clause = self._build_where_clause(filters)
                if where_clause:
                    query_args["where"] = where_clause
            
            # Execute search
            results = self.collection.query(**query_args)
            
            # Map to retrieval results
            retrieval_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]
                    
                    # Convert distance to similarity score
                    similarity_score = 1 - distance
                    
                    result = RetrievalResult(
                        chunk_id=UUID(metadata["chunk_id"]),
                        document_id=UUID(metadata.get("document_id", "00000000-0000-0000-0000-000000000000")),
                        text=results["documents"][0][i] if results["documents"] and results["documents"][0] else "",
                        score=similarity_score,
                        metadata=metadata
                    )
                    retrieval_results.append(result)
            
            logger.debug(f"Found {len(retrieval_results)} similar vectors")
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Failed to search similar vectors: {e}")
            raise VectorRepositoryError(f"Failed to search: {str(e)}")
    
    async def add_vectors(self, embeddings: List[EmbeddingVector]) -> bool:
        """Add vectors to search index"""
        return await self.save_batch(embeddings) is not None
    
    async def update_vector(self, embedding: EmbeddingVector) -> bool:
        """Update vector in search index"""
        # ChromaDB doesn't support updates, so we delete and re-add
        await self.delete(embedding.vector_id)
        await self.save(embedding)
        return True
    
    async def remove_vector(self, vector_id: UUID) -> bool:
        """Remove vector from search index"""
        return await self.delete(vector_id)
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get search index statistics"""
        await self.initialize()
        
        try:
            count = self.collection.count()
            
            return {
                "type": "chroma",
                "collection_name": self.collection_name,
                "vector_count": count,
                "dimension": None,  # ChromaDB doesn't expose this directly
                "metric": "cosine"  # Would get from collection metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise VectorRepositoryError(f"Failed to get stats: {str(e)}")
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build ChromaDB where clause from filters"""
        where_clauses = []
        
        for key, value in filters.items():
            if key == "document_type":
                where_clauses.append({"document_type": value})
            elif key == "model_name":
                where_clauses.append({"model_name": value})
            elif key == "min_score":
                # Score filtering is done after retrieval
                continue
            elif key == "date_range":
                # Date filtering would need to be implemented with metadata
                continue
        
        if len(where_clauses) == 1:
            return where_clauses[0]
        elif len(where_clauses) > 1:
            return {"$and": where_clauses}
        else:
            return {}
    
    def _map_to_domain(self, vector_id: str, embedding: List[float], metadata: Dict[str, Any]) -> EmbeddingVector:
        """Map ChromaDB result to domain entity"""
        return EmbeddingVector(
            vector_id=UUID(vector_id),
            chunk_id=UUID(metadata["chunk_id"]),
            embedding=embedding,
            model_name=metadata["model_name"],
            dimension=len(embedding),
            created_at=datetime.fromisoformat(metadata["created_at"])
        )


class VectorRepositoryError(Exception):
    """Vector repository errors"""
    pass
