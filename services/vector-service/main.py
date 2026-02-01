from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import chromadb
from chromadb.config import Settings
import faiss
import numpy as np
import pickle
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from shared.models.base import (
    EmbeddingVector, RetrievalResult, BaseResponse, ErrorResponse
)
from shared.config.settings import settings
from shared.utils.database import get_db, get_redis
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Vector Store Service starting up...")
    # Initialize vector store
    app.state.vector_store = VectorStore()
    await app.state.vector_store.initialize()
    yield
    logger.info("Vector Store Service shutting down...")

app = FastAPI(
    title="Vector Store Service",
    description="Vector similarity search and storage service",
    version="1.0.0",
    lifespan=lifespan
)


class VectorStore:
    """Vector storage and similarity search implementation."""
    
    def __init__(self):
        self.store_type = settings.vector_store_type
        self.chroma_client = None
        self.chroma_collection = None
        self.faiss_index = None
        self.faiss_id_map = {}  # Maps FAISS IDs to vector IDs
        self.next_faiss_id = 0
    
    async def initialize(self):
        """Initialize the vector store."""
        try:
            if self.store_type == "chroma":
                await self._init_chroma()
            elif self.store_type == "faiss":
                await self._init_faiss()
            else:
                raise ValueError(f"Unsupported vector store type: {self.store_type}")
            
            logger.info(f"Vector store initialized with {self.store_type}")
        except Exception as e:
            logger.error(f"Vector store initialization failed: {e}")
            raise
    
    async def _init_chroma(self):
        """Initialize ChromaDB."""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=settings.chroma_persist_directory
            )
            
            # Get or create collection
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="rag_embeddings",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info("ChromaDB initialized successfully")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            raise
    
    async def _init_faiss(self):
        """Initialize FAISS index."""
        try:
            # Create directory if it doesn't exist
            os.makedirs("./faiss_index", exist_ok=True)
            
            # Try to load existing index
            index_path = "./faiss_index/rag_index.faiss"
            id_map_path = "./faiss_index/id_map.pkl"
            
            if os.path.exists(index_path) and os.path.exists(id_map_path):
                self.faiss_index = faiss.read_index(index_path)
                with open(id_map_path, 'rb') as f:
                    self.faiss_id_map = pickle.load(f)
                self.next_faiss_id = max(self.faiss_id_map.keys()) + 1 if self.faiss_id_map else 0
                logger.info("Loaded existing FAISS index")
            else:
                # Create new index (assuming 384 dimensions for sentence transformers)
                dimension = 384
                self.faiss_index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
                self.faiss_id_map = {}
                self.next_faiss_id = 0
                logger.info("Created new FAISS index")
                
        except Exception as e:
            logger.error(f"FAISS initialization failed: {e}")
            raise
    
    async def add_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """Add vectors to the store."""
        try:
            if self.store_type == "chroma":
                return await self._add_chroma_vectors(vectors)
            elif self.store_type == "faiss":
                return await self._add_faiss_vectors(vectors)
            else:
                raise ValueError(f"Unsupported store type: {self.store_type}")
        except Exception as e:
            logger.error(f"Failed to add vectors: {e}")
            return False
    
    async def _add_chroma_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """Add vectors to ChromaDB."""
        try:
            ids = [vector.vector_id for vector in vectors]
            embeddings = [vector.embedding for vector in vectors]
            metadatas = [
                {
                    "chunk_id": vector.chunk_id,
                    "model_name": vector.model_name,
                    "dimension": vector.dimension,
                    "created_at": vector.created_at.isoformat()
                }
                for vector in vectors
            ]
            
            self.chroma_collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(vectors)} vectors to ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add vectors to ChromaDB: {e}")
            return False
    
    async def _add_faiss_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """Add vectors to FAISS."""
        try:
            embeddings = np.array([vector.embedding for vector in vectors]).astype('float32')
            
            # Normalize for cosine similarity
            faiss.normalize_L2(embeddings)
            
            # Add to index
            faiss_ids = list(range(self.next_faiss_id, self.next_faiss_id + len(vectors)))
            self.faiss_index.add_with_ids(embeddings, np.array(faiss_ids))
            
            # Update ID mapping
            for i, vector in enumerate(vectors):
                self.faiss_id_map[faiss_ids[i]] = vector.vector_id
            
            self.next_faiss_id += len(vectors)
            
            # Save index and ID map
            await self._save_faiss_index()
            
            logger.info(f"Added {len(vectors)} vectors to FAISS")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add vectors to FAISS: {e}")
            return False
    
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[RetrievalResult]:
        """Search for similar vectors."""
        try:
            if self.store_type == "chroma":
                return await self._search_chroma(query_embedding, top_k)
            elif self.store_type == "faiss":
                return await self._search_faiss(query_embedding, top_k)
            else:
                raise ValueError(f"Unsupported store type: {self.store_type}")
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def _search_chroma(self, query_embedding: List[float], top_k: int) -> List[RetrievalResult]:
        """Search in ChromaDB."""
        try:
            results = self.chroma_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "distances", "documents"]
            )
            
            retrieval_results = []
            for i in range(len(results["ids"][0])):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                
                # Convert distance to similarity score (cosine distance to similarity)
                similarity_score = 1 - distance
                
                result = RetrievalResult(
                    chunk_id=metadata["chunk_id"],
                    document_id="",  # Would need to fetch from database
                    text="",  # Would need to fetch from database
                    score=similarity_score,
                    metadata=metadata
                )
                retrieval_results.append(result)
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            return []
    
    async def _search_faiss(self, query_embedding: List[float], top_k: int) -> List[RetrievalResult]:
        """Search in FAISS."""
        try:
            query_vector = np.array([query_embedding]).astype('float32')
            faiss.normalize_L2(query_vector)
            
            similarities, faiss_ids = self.faiss_index.search(query_vector, min(top_k, self.faiss_index.ntotal))
            
            retrieval_results = []
            for i, faiss_id in enumerate(faiss_ids[0]):
                if faiss_id == -1:  # FAISS returns -1 for empty results
                    continue
                
                vector_id = self.faiss_id_map.get(int(faiss_id))
                if vector_id:
                    similarity_score = float(similarities[0][i])
                    
                    result = RetrievalResult(
                        chunk_id="",  # Would need to fetch from database using vector_id
                        document_id="",  # Would need to fetch from database
                        text="",  # Would need to fetch from database
                        score=similarity_score,
                        metadata={"vector_id": vector_id}
                    )
                    retrieval_results.append(result)
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            return []
    
    async def _save_faiss_index(self):
        """Save FAISS index and ID map."""
        try:
            faiss.write_index(self.faiss_index, "./faiss_index/rag_index.faiss")
            with open("./faiss_index/id_map.pkl", 'wb') as f:
                pickle.dump(self.faiss_id_map, f)
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        try:
            if self.store_type == "chroma":
                count = self.chroma_collection.count()
                return {
                    "type": "chroma",
                    "vector_count": count,
                    "collection_name": self.chroma_collection.name
                }
            elif self.store_type == "faiss":
                return {
                    "type": "faiss",
                    "vector_count": self.faiss_index.ntotal,
                    "dimension": self.faiss_index.d
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Database models for metadata
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VectorMetadataDB(Base):
    __tablename__ = "vector_metadata"
    
    vector_id = Column(String, primary_key=True)
    chunk_id = Column(String, nullable=False)
    document_id = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    vector_metadata = Column(JSON)
    created_at = Column(DateTime, nullable=False)


@app.post("/vectors/add", response_model=BaseResponse)
async def add_vectors(
    vectors: List[EmbeddingVector],
    db: Session = Depends(get_db)
):
    """Add vectors to the store."""
    try:
        vector_store = app.state.vector_store
        
        # Add vectors to vector store
        success = await vector_store.add_vectors(vectors)
        
        if success:
            # Save metadata to database
            for vector in vectors:
                # Fetch chunk and document info (simplified)
                metadata_db = VectorMetadataDB(
                    vector_id=vector.vector_id,
                    chunk_id=vector.chunk_id,
                    document_id="",  # Would fetch from chunks table
                    text="",  # Would fetch from chunks table
                    vector_metadata={
                        "model_name": vector.model_name,
                        "dimension": vector.dimension
                    },
                    created_at=vector.created_at
                )
                db.add(metadata_db)
            
            db.commit()
            
            return BaseResponse(
                success=True,
                message=f"Successfully added {len(vectors)} vectors"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to add vectors")
            
    except Exception as e:
        logger.error(f"Add vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectors/search", response_model=List[RetrievalResult])
async def search_vectors(
    query_embedding: List[float],
    top_k: int = 10,
    db: Session = Depends(get_db)
):
    """Search for similar vectors."""
    try:
        vector_store = app.state.vector_store
        
        # Search vectors
        results = await vector_store.search(query_embedding, top_k)
        
        # Enrich with text and document information
        for result in results:
            if result.chunk_id:
                # Fetch chunk details from database
                chunk_query = db.query(VectorMetadataDB).filter(
                    VectorMetadataDB.chunk_id == result.chunk_id
                ).first()
                
                if chunk_query:
                    result.document_id = chunk_query.document_id
                    result.text = chunk_query.text
                    result.metadata.update(chunk_query.vector_metadata or {})
        
        return results
        
    except Exception as e:
        logger.error(f"Search vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vectors/stats")
async def get_vector_stats():
    """Get vector store statistics."""
    vector_store = app.state.vector_store
    stats = await vector_store.get_stats()
    return stats


@app.delete("/vectors/{vector_id}")
async def delete_vector(
    vector_id: str,
    db: Session = Depends(get_db)
):
    """Delete a vector from the store."""
    try:
        vector_store = app.state.vector_store
        
        # Remove from vector store (implementation depends on store type)
        if vector_store.store_type == "chroma":
            vector_store.chroma_collection.delete(ids=[vector_id])
        elif vector_store.store_type == "faiss":
            # FAISS doesn't support easy deletion, would need to rebuild index
            logger.warning("FAISS deletion not implemented - would require index rebuild")
        
        # Remove metadata from database
        metadata = db.query(VectorMetadataDB).filter(
            VectorMetadataDB.vector_id == vector_id
        ).first()
        
        if metadata:
            db.delete(metadata)
            db.commit()
        
        return {"message": f"Vector {vector_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Delete vector error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    vector_store = app.state.vector_store
    stats = await vector_store.get_stats()
    return {
        "status": "healthy",
        "service": "vector-service",
        "store_type": vector_store.store_type,
        "stats": stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=settings.debug
    )
