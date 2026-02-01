from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import torch
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import logging
from typing import List, Dict, Any, Optional
import asyncio
import psutil
import gc
from datetime import datetime
import json

from shared.models.base import (
    EmbeddingVector, TextChunk, ModelType, BaseResponse,
    ErrorResponse, ModelInfo
)
from shared.config.settings import settings
from shared.utils.database import get_db, get_redis, get_clickhouse
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Embedding Service starting up...")
    # Initialize model manager
    app.state.model_manager = ModelManager()
    await app.state.model_manager.initialize()
    yield
    logger.info("Embedding Service shutting down...")
    await app.state.model_manager.cleanup()

app = FastAPI(
    title="Embedding Service",
    description="Text embedding generation service with HuggingFace models",
    version="1.0.0",
    lifespan=lifespan
)


class ModelManager:
    """Manages embedding models with memory constraints."""
    
    def __init__(self):
        self.models: Dict[str, SentenceTransformer] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}
        self.max_memory_gb = settings.max_memory_gb
        self.current_memory_usage = 0
        self.model_usage_stats: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize default embedding model."""
        try:
            await self.load_model(settings.embedding_model)
            logger.info(f"Loaded default embedding model: {settings.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load default model: {e}")
            raise
    
    def _get_model_memory_usage(self, model_name: str) -> int:
        """Estimate memory usage of a model in MB."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss // (1024 * 1024)  # Convert to MB
        except Exception:
            return 0
    
    def _check_memory_availability(self, required_memory_mb: int) -> bool:
        """Check if enough memory is available."""
        current_usage = self._get_model_memory_usage("current")
        available_memory = self.max_memory_gb * 1024 - current_usage
        return available_memory >= required_memory_mb
    
    async def load_model(self, model_name: str) -> bool:
        """Load embedding model with memory management."""
        if model_name in self.models:
            self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
            return True
        
        try:
            # Check memory availability
            estimated_memory = 1000  # Rough estimate in MB
            if not self._check_memory_availability(estimated_memory):
                await self._unload_least_used_model()
            
            # Load model with configurable timeout
            logger.info(f"Loading model: {model_name}")
            import os
            os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = str(settings.hf_download_timeout)
            model = SentenceTransformer(
                model_name,
                cache_folder=settings.hf_cache_dir
            )
            
            # Test model
            test_embedding = model.encode(["test"], show_progress_bar=False)
            
            self.models[model_name] = model
            self.model_usage_stats[model_name] = {
                "loaded_at": datetime.utcnow(),
                "last_used": datetime.utcnow(),
                "request_count": 0,
                "dimension": len(test_embedding[0])
            }
            
            logger.info(f"Successfully loaded model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    async def _unload_least_used_model(self):
        """Unload the least recently used model."""
        if not self.models:
            return
        
        # Find least recently used model
        lru_model = min(
            self.model_usage_stats.items(),
            key=lambda x: x[1]["last_used"]
        )[0]
        
        if lru_model != settings.embedding_model:  # Don't unload default model
            await self.unload_model(lru_model)
            logger.info(f"Unloaded LRU model: {lru_model}")
    
    async def unload_model(self, model_name: str):
        """Unload a model to free memory."""
        if model_name in self.models:
            del self.models[model_name]
            del self.model_usage_stats[model_name]
            gc.collect()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
    
    async def get_embedding(self, text: str, model_name: str = None) -> List[float]:
        """Generate embedding for text."""
        if model_name is None:
            model_name = settings.embedding_model
        
        if model_name not in self.models:
            if not await self.load_model(model_name):
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to load model: {model_name}"
                )
        
        model = self.models[model_name]
        self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
        self.model_usage_stats[model_name]["request_count"] += 1
        
        try:
            embedding = model.encode(
                text,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail="Embedding generation failed")
    
    async def get_batch_embeddings(self, texts: List[str], model_name: str = None) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if model_name is None:
            model_name = settings.embedding_model
        
        if model_name not in self.models:
            if not await self.load_model(model_name):
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load model: {model_name}"
                )
        
        model = self.models[model_name]
        self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
        self.model_usage_stats[model_name]["request_count"] += len(texts)
        
        try:
            embeddings = model.encode(
                texts,
                show_progress_bar=False,
                batch_size=32,
                convert_to_numpy=True
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail="Batch embedding generation failed")
    
    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about loaded models."""
        if model_name:
            if model_name in self.models:
                stats = self.model_usage_stats[model_name]
                return {
                    "model_name": model_name,
                    "dimension": stats["dimension"],
                    "loaded_at": stats["loaded_at"],
                    "last_used": stats["last_used"],
                    "request_count": stats["request_count"],
                    "memory_usage_mb": self._get_model_memory_usage(model_name)
                }
            else:
                return {}
        else:
            return {
                name: self.get_model_info(name)
                for name in self.models.keys()
            }
    
    async def cleanup(self):
        """Cleanup resources."""
        for model_name in list(self.models.keys()):
            await self.unload_model(model_name)


# Database models
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class EmbeddingDB(Base):
    __tablename__ = "embeddings"
    
    vector_id = Column(String, primary_key=True)
    chunk_id = Column(String, nullable=False)
    embedding = Column(Text, nullable=False)  # Store as JSON string
    model_name = Column(String, nullable=False)
    dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


@app.post("/embeddings/generate", response_model=EmbeddingVector)
async def generate_embedding(
    chunk_id: str,
    text: str,
    model_name: Optional[str] = None,
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """Generate embedding for a single text chunk."""
    try:
        model_manager = app.state.model_manager
        
        # Generate embedding
        embedding = await model_manager.get_embedding(text, model_name)
        
        # Create embedding vector
        embedding_vector = EmbeddingVector(
            chunk_id=chunk_id,
            embedding=embedding,
            model_name=model_name or settings.embedding_model,
            dimension=len(embedding)
        )
        
        # Save to database
        embedding_db = EmbeddingDB(
            vector_id=embedding_vector.vector_id,
            chunk_id=embedding_vector.chunk_id,
            embedding=json.dumps(embedding),
            model_name=embedding_vector.model_name,
            dimension=embedding_vector.dimension,
            created_at=embedding_vector.created_at
        )
        db.add(embedding_db)
        db.commit()
        
        # Cache in Redis
        await redis_client.setex(
            f"embedding:{chunk_id}",
            3600,  # 1 hour
            json.dumps({
                "vector_id": embedding_vector.vector_id,
                "embedding": embedding,
                "model_name": embedding_vector.model_name,
                "dimension": embedding_vector.dimension
            })
        )
        
        # Log to ClickHouse for analytics
        clickhouse_client = get_clickhouse()
        try:
            clickhouse_client.execute(
                "INSERT INTO model_metrics VALUES",
                [{
                    'timestamp': datetime.utcnow(),
                    'model_name': embedding_vector.model_name,
                    'model_type': 'embedding',
                    'memory_usage_mb': model_manager._get_model_memory_usage(embedding_vector.model_name),
                    'request_count': 1,
                    'avg_processing_time_ms': 0  # Would need to measure actual time
                }]
            )
        except Exception as e:
            logger.warning(f"Failed to log to ClickHouse: {e}")
        
        return embedding_vector
        
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embeddings/batch", response_model=List[EmbeddingVector])
async def generate_batch_embeddings(
    chunks: List[Dict[str, str]],  # [{"chunk_id": "...", "text": "..."}]
    model_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate embeddings for multiple text chunks."""
    try:
        model_manager = app.state.model_manager
        
        chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate batch embeddings
        embeddings = await model_manager.get_batch_embeddings(texts, model_name)
        
        # Create embedding vectors
        embedding_vectors = []
        for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
            vector = EmbeddingVector(
                chunk_id=chunk_id,
                embedding=embedding,
                model_name=model_name or settings.embedding_model,
                dimension=len(embedding)
            )
            embedding_vectors.append(vector)
            
            # Save to database
            embedding_db = EmbeddingDB(
                vector_id=vector.vector_id,
                chunk_id=vector.chunk_id,
                embedding=json.dumps(embedding),
                model_name=vector.model_name,
                dimension=vector.dimension,
                created_at=vector.created_at
            )
            db.add(embedding_db)
        
        db.commit()
        
        return embedding_vectors
        
    except Exception as e:
        logger.error(f"Batch embedding generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List available embedding models."""
    model_manager = app.state.model_manager
    models_info = []
    
    for model_name, stats in model_manager.model_usage_stats.items():
        model_info = ModelInfo(
            name=model_name,
            type=ModelType.EMBEDDING,
            version="1.0.0",  # Would get from model config
            status="loaded",
            memory_usage_mb=model_manager._get_model_memory_usage(model_name),
            loaded_at=stats["loaded_at"],
            last_used=stats["last_used"],
            config={
                "dimension": stats["dimension"],
                "request_count": stats["request_count"]
            }
        )
        models_info.append(model_info)
    
    return models_info


@app.post("/models/{model_name}/load")
async def load_model(model_name: str):
    """Load a specific embedding model."""
    model_manager = app.state.model_manager
    success = await model_manager.load_model(model_name)
    
    if success:
        return {"message": f"Model {model_name} loaded successfully"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to load model {model_name}")


@app.delete("/models/{model_name}/unload")
async def unload_model(model_name: str):
    """Unload a specific embedding model."""
    model_manager = app.state.model_manager
    await model_manager.unload_model(model_name)
    return {"message": f"Model {model_name} unloaded successfully"}


@app.get("/embeddings/{chunk_id}")
async def get_embedding(
    chunk_id: str,
    redis_client = Depends(get_redis)
):
    """Get embedding for a specific chunk."""
    # Try cache first
    cached = await redis_client.get(f"embedding:{chunk_id}")
    if cached:
        data = json.loads(cached)
        return data
    
    # Query database
    db = next(get_db())
    embedding = db.query(EmbeddingDB).filter(EmbeddingDB.chunk_id == chunk_id).first()
    
    if not embedding:
        raise HTTPException(status_code=404, detail="Embedding not found")
    
    return {
        "vector_id": embedding.vector_id,
        "chunk_id": embedding.chunk_id,
        "embedding": json.loads(embedding.embedding),
        "model_name": embedding.model_name,
        "dimension": embedding.dimension,
        "created_at": embedding.created_at
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    model_manager = app.state.model_manager
    return {
        "status": "healthy",
        "service": "embedding-service",
        "loaded_models": list(model_manager.models.keys()),
        "memory_usage_mb": model_manager._get_model_memory_usage("current")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=settings.debug
    )
