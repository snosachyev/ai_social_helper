"""Sentence Transformers implementation of embedding provider"""

from typing import List, Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
import psutil
import gc
import torch

from sentence_transformers import SentenceTransformer

from ...domain.entities.embedding import EmbeddingVector
from ...domain.services.retrieval_service import EmbeddingProvider
from ...infrastructure.config.settings import get_config


logger = logging.getLogger(__name__)


class SentenceTransformerProvider(EmbeddingProvider):
    """Sentence Transformers implementation of EmbeddingProvider"""
    
    def __init__(self):
        self.models: Dict[str, SentenceTransformer] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}
        self.max_memory_gb = 16
        self.current_memory_usage = 0
        self.model_usage_stats: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the provider with default model"""
        if self._initialized:
            return
        
        try:
            config = await get_config()
            self.max_memory_gb = config.model.max_memory_gb
            
            # Load default model
            default_model = config.model.embedding_model
            await self._load_model(default_model)
            
            self._initialized = True
            logger.info(f"SentenceTransformerProvider initialized with model: {default_model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformerProvider: {e}")
            raise EmbeddingProviderError(f"Failed to initialize: {str(e)}")
    
    async def generate_embedding(self, text: str, model_name: str) -> EmbeddingVector:
        """Generate embedding for text"""
        await self.initialize()
        
        if model_name not in self.models:
            if not await self._load_model(model_name):
                raise EmbeddingProviderError(f"Failed to load model: {model_name}")
        
        model = self.models[model_name]
        
        try:
            # Update usage stats
            self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
            self.model_usage_stats[model_name]["request_count"] += 1
            
            # Generate embedding
            embedding = model.encode(
                text,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Create embedding vector
            embedding_vector = EmbeddingVector(
                chunk_id=None,  # Will be set by caller
                embedding=embedding.tolist(),
                model_name=model_name,
                dimension=len(embedding)
            )
            
            return embedding_vector
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise EmbeddingProviderError(f"Failed to generate embedding: {str(e)}")
    
    async def generate_batch_embeddings(self, texts: List[str], model_name: str) -> List[EmbeddingVector]:
        """Generate embeddings for multiple texts"""
        await self.initialize()
        
        if model_name not in self.models:
            if not await self._load_model(model_name):
                raise EmbeddingProviderError(f"Failed to load model: {model_name}")
        
        model = self.models[model_name]
        
        try:
            # Update usage stats
            self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
            self.model_usage_stats[model_name]["request_count"] += len(texts)
            
            # Generate batch embeddings
            config = await get_config()
            embeddings = model.encode(
                texts,
                show_progress_bar=False,
                batch_size=config.model.batch_size,
                convert_to_numpy=True
            )
            
            # Create embedding vectors
            embedding_vectors = []
            for embedding in embeddings:
                vector = EmbeddingVector(
                    chunk_id=None,  # Will be set by caller
                    embedding=embedding.tolist(),
                    model_name=model_name,
                    dimension=len(embedding)
                )
                embedding_vectors.append(vector)
            
            return embedding_vectors
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise EmbeddingProviderError(f"Failed to generate batch embeddings: {str(e)}")
    
    async def _load_model(self, model_name: str) -> bool:
        """Load a model with memory management"""
        if model_name in self.models:
            self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
            return True
        
        try:
            # Check memory availability
            estimated_memory = 1000  # Rough estimate in MB
            if not self._check_memory_availability(estimated_memory):
                await self._unload_least_used_model()
            
            # Load model
            logger.info(f"Loading model: {model_name}")
            config = await get_config()
            
            model = SentenceTransformer(
                model_name,
                cache_folder=config.model.cache_dir,
                device=config.model.device
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
    
    def _check_memory_availability(self, required_memory_mb: int) -> bool:
        """Check if enough memory is available"""
        try:
            current_usage = self._get_model_memory_usage("current")
            available_memory = self.max_memory_gb * 1024 - current_usage
            return available_memory >= required_memory_mb
        except Exception:
            return False
    
    def _get_model_memory_usage(self, model_name: str) -> int:
        """Estimate memory usage of a model in MB"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss // (1024 * 1024)  # Convert to MB
        except Exception:
            return 0
    
    async def _unload_least_used_model(self):
        """Unload the least recently used model"""
        if not self.models:
            return
        
        try:
            config = await get_config()
            default_model = config.model.embedding_model
            
            # Find least recently used model (excluding default)
            lru_candidates = [
                (name, stats) for name, stats in self.model_usage_stats.items()
                if name != default_model
            ]
            
            if not lru_candidates:
                return
            
            lru_model = min(lru_candidates, key=lambda x: x[1]["last_used"])[0]
            await self._unload_model(lru_model)
            logger.info(f"Unloaded LRU model: {lru_model}")
            
        except Exception as e:
            logger.error(f"Failed to unload LRU model: {e}")
    
    async def _unload_model(self, model_name: str):
        """Unload a model to free memory"""
        if model_name in self.models:
            del self.models[model_name]
            del self.model_usage_stats[model_name]
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about loaded models"""
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
        """Cleanup resources"""
        for model_name in list(self.models.keys()):
            await self._unload_model(model_name)
        logger.info("SentenceTransformerProvider cleaned up")


class EmbeddingProviderError(Exception):
    """Embedding provider errors"""
    pass
