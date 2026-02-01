from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import httpx
import os
import shutil
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
import json
import psutil

from shared.models.base import (
    ModelInfo, ModelType, BaseResponse, ErrorResponse
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
    logger.info("Model Management Service starting up...")
    # Initialize model manager
    app.state.model_manager = CentralModelManager()
    await app.state.model_manager.initialize()
    yield
    logger.info("Model Management Service shutting down...")

app = FastAPI(
    title="Model Management Service",
    description="Central model downloading, caching, and resource allocation service",
    version="1.0.0",
    lifespan=lifespan
)


class CentralModelManager:
    """Central model management with resource allocation."""
    
    def __init__(self):
        self.hf_cache_dir = Path(settings.hf_cache_dir)
        self.max_memory_gb = settings.max_memory_gb
        self.model_registry: Dict[str, Dict[str, Any]] = {}
        self.service_clients = {
            "embedding": httpx.AsyncClient(timeout=60.0),
            "generation": httpx.AsyncClient(timeout=60.0)
        }
        self.service_urls = {
            "embedding": "http://embedding-service:8002",
            "generation": "http://generation-service:8005"
        }
    
    async def initialize(self):
        """Initialize the model manager."""
        try:
            # Ensure cache directory exists
            self.hf_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Scan existing models in cache
            await self._scan_cached_models()
            
            # Initialize model registry with default models
            await self._register_default_models()
            
            logger.info("Model Manager initialized successfully")
        except Exception as e:
            logger.error(f"Model Manager initialization failed: {e}")
            raise
    
    async def _scan_cached_models(self):
        """Scan existing models in HuggingFace cache."""
        try:
            # Look for model directories in cache
            for model_dir in self.hf_cache_dir.iterdir():
                if model_dir.is_dir():
                    # Try to identify model type and metadata
                    model_info = await self._analyze_cached_model(model_dir)
                    if model_info:
                        self.model_registry[model_info["name"]] = model_info
            
            logger.info(f"Scanned {len(self.model_registry)} cached models")
        except Exception as e:
            logger.error(f"Failed to scan cached models: {e}")
    
    async def _analyze_cached_model(self, model_dir: Path) -> Optional[Dict[str, Any]]:
        """Analyze a cached model directory to extract metadata."""
        try:
            # Look for config file
            config_file = model_dir / "config.json"
            if not config_file.exists():
                return None
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Determine model type based on architecture
            model_type = self._determine_model_type(config)
            
            # Calculate model size
            model_size = self._calculate_model_size(model_dir)
            
            return {
                "name": model_dir.name,
                "type": model_type,
                "path": str(model_dir),
                "size_mb": model_size,
                "config": config,
                "cached_at": datetime.fromtimestamp(model_dir.stat().st_mtime),
                "status": "cached"
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze model {model_dir}: {e}")
            return None
    
    def _determine_model_type(self, config: Dict[str, Any]) -> ModelType:
        """Determine model type from config."""
        architecture = config.get("architectures", [])
        if not architecture:
            return ModelType.EMBEDDING  # Default
        
        arch = architecture[0].lower()
        
        if any(keyword in arch for keyword in ["causallm", "gpt", "bert", "roberta"]):
            if "embedding" in arch or "sentence" in arch:
                return ModelType.EMBEDDING
            else:
                return ModelType.GENERATION
        elif "rerank" in arch:
            return ModelType.RERANKING
        else:
            return ModelType.EMBEDDING  # Default
    
    def _calculate_model_size(self, model_dir: Path) -> int:
        """Calculate model size in MB."""
        try:
            total_size = 0
            for file_path in model_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size // (1024 * 1024)  # Convert to MB
        except Exception:
            return 0
    
    async def _register_default_models(self):
        """Register default models in the registry."""
        default_models = [
            {
                "name": settings.embedding_model,
                "type": ModelType.EMBEDDING,
                "description": "Default embedding model",
                "priority": "high"
            },
            {
                "name": settings.generation_model,
                "type": ModelType.GENERATION,
                "description": "Default generation model",
                "priority": "high"
            }
        ]
        
        for model in default_models:
            if model["name"] not in self.model_registry:
                self.model_registry[model["name"]] = {
                    "name": model["name"],
                    "type": model["type"].value,
                    "description": model["description"],
                    "priority": model["priority"],
                    "status": "registered",
                    "cached_at": None
                }
    
    async def download_model(self, model_name: str, model_type: ModelType) -> bool:
        """Download model from HuggingFace Hub."""
        try:
            logger.info(f"Downloading model: {model_name}")
            
            # Check if model already exists
            if model_name in self.model_registry and self.model_registry[model_name]["status"] == "cached":
                logger.info(f"Model {model_name} already cached")
                return True
            
            # Use huggingface_hub to download model
            from huggingface_hub import snapshot_download
            
            # Download model
            model_path = snapshot_download(
                repo_id=model_name,
                cache_dir=self.hf_cache_dir,
                ignore_patterns=["*.pt", "*.bin"] if model_type == ModelType.EMBEDDING else []
            )
            
            # Update registry
            model_info = await self._analyze_cached_model(Path(model_path))
            if model_info:
                model_info["status"] = "cached"
                model_info["type"] = model_type.value
                self.model_registry[model_name] = model_info
            
            logger.info(f"Successfully downloaded model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            return False
    
    async def load_model_to_service(self, model_name: str, model_type: ModelType) -> bool:
        """Load model to appropriate service."""
        try:
            service_name = model_type.value
            service_url = self.service_urls.get(service_name)
            
            if not service_url:
                raise ValueError(f"No service found for model type: {model_type}")
            
            client = self.service_clients[service_name]
            
            # Call service to load model
            response = await client.post(f"{service_url}/models/{model_name}/load")
            response.raise_for_status()
            
            # Update registry
            if model_name in self.model_registry:
                self.model_registry[model_name]["status"] = "loaded"
                self.model_registry[model_name]["loaded_at"] = datetime.utcnow()
            
            logger.info(f"Successfully loaded model {model_name} to {service_name} service")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    async def unload_model_from_service(self, model_name: str, model_type: ModelType) -> bool:
        """Unload model from service."""
        try:
            service_name = model_type.value
            service_url = self.service_urls.get(service_name)
            
            if not service_url:
                return False
            
            client = self.service_clients[service_name]
            
            # Call service to unload model
            response = await client.delete(f"{service_url}/models/{model_name}/unload")
            response.raise_for_status()
            
            # Update registry
            if model_name in self.model_registry:
                self.model_registry[model_name]["status"] = "cached"
                self.model_registry[model_name]["unloaded_at"] = datetime.utcnow()
            
            logger.info(f"Successfully unloaded model {model_name} from {service_name} service")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload model {model_name}: {e}")
            return False
    
    async def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage(self.hf_cache_dir)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "memory_total_gb": memory.total // (1024**3),
                "memory_available_gb": memory.available // (1024**3),
                "memory_usage_percent": memory.percent,
                "disk_total_gb": disk.total // (1024**3),
                "disk_available_gb": disk.free // (1024**3),
                "disk_usage_percent": (disk.used / disk.total) * 100,
                "cpu_usage_percent": cpu_percent,
                "cache_directory": str(self.hf_cache_dir)
            }
            
        except Exception as e:
            logger.error(f"Failed to get system resources: {e}")
            return {}
    
    async def cleanup_old_models(self, days_old: int = 30) -> int:
        """Clean up old models from cache."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            cleaned_count = 0
            
            for model_name, model_info in list(self.model_registry.items()):
                if (model_info["status"] == "cached" and 
                    model_info.get("cached_at") and 
                    model_info["cached_at"] < cutoff_date and
                    model_info.get("priority") != "high"):
                    
                    # Remove model from cache
                    model_path = Path(model_info.get("path", ""))
                    if model_path.exists():
                        shutil.rmtree(model_path)
                        del self.model_registry[model_name]
                        cleaned_count += 1
                        logger.info(f"Cleaned up old model: {model_name}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old models: {e}")
            return 0


# Database models for model registry
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ModelRegistryDB(Base):
    __tablename__ = "model_registry"
    
    model_name = Column(String, primary_key=True)
    model_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    size_mb = Column(Integer)
    path = Column(Text)
    config = Column(JSON)
    cached_at = Column(DateTime)
    loaded_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List all registered models."""
    try:
        model_manager = app.state.model_manager
        models_info = []
        
        for model_name, model_info in model_manager.model_registry.items():
            model_info_obj = ModelInfo(
                name=model_name,
                type=ModelType(model_info["type"]),
                version="1.0.0",
                status=model_info["status"],
                memory_usage_mb=model_info.get("size_mb", 0),
                loaded_at=model_info.get("loaded_at"),
                last_used=model_info.get("last_used"),
                config=model_info.get("config", {})
            )
            models_info.append(model_info_obj)
        
        return models_info
        
    except Exception as e:
        logger.error(f"List models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/{model_name}/download")
async def download_model(
    model_name: str,
    model_type: ModelType,
    db: Session = Depends(get_db)
):
    """Download a model from HuggingFace Hub."""
    try:
        model_manager = app.state.model_manager
        
        # Download model
        success = await model_manager.download_model(model_name, model_type)
        
        if success:
            # Save to database
            model_info = model_manager.model_registry.get(model_name, {})
            model_db = ModelRegistryDB(
                model_name=model_name,
                model_type=model_type.value,
                status=model_info.get("status", "downloaded"),
                size_mb=model_info.get("size_mb"),
                path=model_info.get("path"),
                config=model_info.get("config"),
                cached_at=model_info.get("cached_at"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.merge(model_db)  # merge to handle existing records
            db.commit()
            
            return {"message": f"Model {model_name} downloaded successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to download model {model_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/{model_name}/load")
async def load_model(
    model_name: str,
    model_type: ModelType,
    db: Session = Depends(get_db)
):
    """Load a model to the appropriate service."""
    try:
        model_manager = app.state.model_manager
        
        # Ensure model is downloaded
        if model_name not in model_manager.model_registry:
            # Download first
            download_success = await model_manager.download_model(model_name, model_type)
            if not download_success:
                raise HTTPException(status_code=404, detail=f"Model {model_name} not found and download failed")
        
        # Load to service
        success = await model_manager.load_model_to_service(model_name, model_type)
        
        if success:
            # Update database
            model_db = db.query(ModelRegistryDB).filter(
                ModelRegistryDB.model_name == model_name
            ).first()
            
            if model_db:
                model_db.status = "loaded"
                model_db.loaded_at = datetime.utcnow()
                model_db.updated_at = datetime.utcnow()
                db.commit()
            
            return {"message": f"Model {model_name} loaded successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to load model {model_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/models/{model_name}/unload")
async def unload_model(
    model_name: str,
    model_type: ModelType,
    db: Session = Depends(get_db)
):
    """Unload a model from service."""
    try:
        model_manager = app.state.model_manager
        
        # Unload from service
        success = await model_manager.unload_model_from_service(model_name, model_type)
        
        if success:
            # Update database
            model_db = db.query(ModelRegistryDB).filter(
                ModelRegistryDB.model_name == model_name
            ).first()
            
            if model_db:
                model_db.status = "cached"
                model_db.updated_at = datetime.utcnow()
                db.commit()
            
            return {"message": f"Model {model_name} unloaded successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to unload model {model_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unload model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/models/{model_name}")
async def delete_model(
    model_name: str,
    db: Session = Depends(get_db)
):
    """Delete a model from cache."""
    try:
        model_manager = app.state.model_manager
        
        if model_name not in model_manager.model_registry:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        model_info = model_manager.model_registry[model_name]
        
        # Remove from cache directory
        model_path = Path(model_info.get("path", ""))
        if model_path.exists():
            shutil.rmtree(model_path)
        
        # Remove from registry
        del model_manager.model_registry[model_name]
        
        # Remove from database
        model_db = db.query(ModelRegistryDB).filter(
            ModelRegistryDB.model_name == model_name
        ).first()
        
        if model_db:
            db.delete(model_db)
            db.commit()
        
        return {"message": f"Model {model_name} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/system/resources")
async def get_system_resources():
    """Get system resource information."""
    model_manager = app.state.model_manager
    resources = await model_manager.get_system_resources()
    return resources


@app.post("/system/cleanup")
async def cleanup_old_models(days_old: int = 30):
    """Clean up old models from cache."""
    model_manager = app.state.model_manager
    cleaned_count = await model_manager.cleanup_old_models(days_old)
    return {"message": f"Cleaned up {cleaned_count} old models"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    model_manager = app.state.model_manager
    return {
        "status": "healthy",
        "service": "model-service",
        "registered_models": len(model_manager.model_registry)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=settings.debug
    )
