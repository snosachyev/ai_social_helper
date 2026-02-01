from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import logging
from typing import List, Dict, Any, Optional
import asyncio
import psutil
import gc
from datetime import datetime
import json

from shared.models.base import (
    GenerationRequest, GenerationResponse, RetrievalResult,
    ModelType, BaseResponse, ErrorResponse, ModelInfo
)
from shared.config.settings import settings
from shared.utils.database import get_db, get_redis, get_clickhouse
from sqlalchemy.orm import Session
from .llm_providers import LLMProviderManager, OpenAIProvider, LocalLLMProvider

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Generation Service starting up...")
    # Initialize model manager
    app.state.model_manager = GenerationModelManager()
    await app.state.model_manager.initialize()
    
    # Initialize LLM provider manager
    app.state.llm_manager = LLMProviderManager()
    
    # Register local provider
    local_provider = LocalLLMProvider(app.state.model_manager)
    app.state.llm_manager.register_provider("local", local_provider, is_default=True)
    
    # Register OpenAI provider if configured
    if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
        openai_provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=getattr(settings, 'openai_base_url', None)
        )
        app.state.llm_manager.register_provider("openai", openai_provider)
        logger.info("OpenAI provider registered")
    
    yield
    logger.info("Generation Service shutting down...")
    await app.state.model_manager.cleanup()

app = FastAPI(
    title="Generation Service",
    description="LLM inference and response generation service",
    version="1.0.0",
    lifespan=lifespan
)


class GenerationModelManager:
    """Manages generation models with memory constraints."""
    
    def __init__(self):
        self.models: Dict[str, Any] = {}  # Stores model pipelines
        self.tokenizers: Dict[str, Any] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}
        self.max_memory_gb = settings.max_memory_gb
        self.model_usage_stats: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize default generation model."""
        try:
            await self.load_model(settings.generation_model)
            logger.info(f"Loaded default generation model: {settings.generation_model}")
        except Exception as e:
            logger.error(f"Failed to load default model: {e}")
            # Don't raise - service can start without default model
    
    def _get_model_memory_usage(self) -> int:
        """Estimate current memory usage in MB."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss // (1024 * 1024)
        except Exception:
            return 0
    
    def _check_memory_availability(self, required_memory_mb: int) -> bool:
        """Check if enough memory is available."""
        current_usage = self._get_model_memory_usage()
        available_memory = self.max_memory_gb * 1024 - current_usage
        return available_memory >= required_memory_mb
    
    async def load_model(self, model_name: str) -> bool:
        """Load generation model with memory management."""
        if model_name in self.models:
            self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
            return True
        
        try:
            # Check memory availability
            estimated_memory = 2000  # Rough estimate in MB for generation models
            if not self._check_memory_availability(estimated_memory):
                await self._unload_least_used_model()
            
            logger.info(f"Loading generation model: {model_name}")
            
            # Load tokenizer and model
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=settings.hf_cache_dir
            )
            
            # Add padding token if not present
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                cache_dir=settings.hf_cache_dir,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
            
            # Create pipeline
            generator = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device=0 if torch.cuda.is_available() else -1
            )
            
            self.models[model_name] = generator
            self.tokenizers[model_name] = tokenizer
            self.model_usage_stats[model_name] = {
                "loaded_at": datetime.utcnow(),
                "last_used": datetime.utcnow(),
                "request_count": 0,
                "total_tokens_generated": 0
            }
            
            logger.info(f"Successfully loaded generation model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load generation model {model_name}: {e}")
            return False
    
    async def _unload_least_used_model(self):
        """Unload the least recently used model."""
        if not self.models:
            return
        
        # Find least recently used model (but keep default if possible)
        lru_model = min(
            [(name, stats) for name, stats in self.model_usage_stats.items() 
             if name != settings.generation_model],
            key=lambda x: x[1]["last_used"],
            default=(None, None)
        )[0]
        
        if lru_model:
            await self.unload_model(lru_model)
            logger.info(f"Unloaded LRU model: {lru_model}")
    
    async def unload_model(self, model_name: str):
        """Unload a model to free memory."""
        if model_name in self.models:
            del self.models[model_name]
            del self.tokenizers[model_name]
            del self.model_usage_stats[model_name]
            gc.collect()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
    
    async def generate_response(
        self, 
        query: str, 
        context: List[RetrievalResult], 
        model_name: str = None,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """Generate response based on query and context."""
        if model_name is None:
            model_name = settings.generation_model
        
        if model_name not in self.models:
            if not await self.load_model(model_name):
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load model: {model_name}"
                )
        
        generator = self.models[model_name]
        self.model_usage_stats[model_name]["last_used"] = datetime.utcnow()
        self.model_usage_stats[model_name]["request_count"] += 1
        
        try:
            # Create prompt with context
            prompt = self._create_prompt(query, context)
            
            # Generate response
            response = generator(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=generator.tokenizer.eos_token_id,
                num_return_sequences=1
            )
            
            # Extract generated text
            generated_text = response[0]["generated_text"]
            
            # Remove the prompt from the response
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            # Update stats
            tokens_generated = len(generator.tokenizer.encode(generated_text))
            self.model_usage_stats[model_name]["total_tokens_generated"] += tokens_generated
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            raise HTTPException(status_code=500, detail="Response generation failed")
    
    def _create_prompt(self, query: str, context: List[RetrievalResult]) -> str:
        """Create a prompt with context for the model."""
        context_text = "\n\n".join([
            f"Context {i+1}: {result.text}"
            for i, result in enumerate(context[:5])  # Limit context to top 5
        ])
        
        prompt = f"""Based on the following context, please answer the question.

Context:
{context_text}

Question: {query}

Answer:"""
        
        return prompt
    
    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about loaded models."""
        if model_name:
            if model_name in self.models:
                stats = self.model_usage_stats[model_name]
                return {
                    "model_name": model_name,
                    "loaded_at": stats["loaded_at"],
                    "last_used": stats["last_used"],
                    "request_count": stats["request_count"],
                    "total_tokens_generated": stats["total_tokens_generated"],
                    "memory_usage_mb": self._get_model_memory_usage()
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


# Database models for generation history
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class GenerationHistoryDB(Base):
    __tablename__ = "generation_history"
    
    request_id = Column(String, primary_key=True)
    query = Column(Text, nullable=False)
    context = Column(JSON, nullable=False)
    response = Column(Text, nullable=False)
    model_name = Column(String, nullable=False)
    tokens_used = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


@app.post("/generate", response_model=GenerationResponse)
async def generate_response(
    generation_request: GenerationRequest,
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """Generate a response based on query and context."""
    try:
        llm_manager = app.state.llm_manager
        model_manager = app.state.model_manager
        
        # Extract provider and model from request
        provider_name = generation_request.metadata.get("provider") if generation_request.metadata else None
        model_name = generation_request.model_name
        
        # Generate response
        start_time = datetime.utcnow()
        response_text = await llm_manager.generate_response(
            query=generation_request.query,
            context=generation_request.context,
            provider_name=provider_name,
            model_name=model_name,
            max_tokens=generation_request.max_tokens,
            temperature=generation_request.temperature,
            stream=generation_request.metadata.get("stream", False) if generation_request.metadata else False
        )
        
        # Handle streaming response
        if generation_request.metadata and generation_request.metadata.get("stream", False):
            # For streaming, we'd need to implement Server-Sent Events
            # For now, convert generator to string
            if hasattr(response_text, '__aiter__'):
                response_text = "".join([chunk async for chunk in response_text])
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Count tokens
        tokens_used = await llm_manager.count_tokens(
            response_text, 
            provider_name=provider_name, 
            model_name=model_name
        )
        
        # Create response
        generation_response = GenerationResponse(
            request_id=generation_request.request_id,
            response=response_text,
            model_name=model_name,
            tokens_used=tokens_used,
            processing_time_ms=int(processing_time),
            metadata={
                **(generation_request.metadata or {}),
                "provider": provider_name or "local"
            }
        )
        
        # Save to database
        generation_history = GenerationHistoryDB(
            request_id=generation_response.request_id,
            query=generation_request.query,
            context=[result.dict() for result in generation_request.context],
            response=generation_response.response,
            model_name=generation_response.model_name,
            tokens_used=generation_response.tokens_used,
            processing_time_ms=generation_response.processing_time_ms,
            created_at=datetime.utcnow()
        )
        db.add(generation_history)
        db.commit()
        
        # Cache in Redis
        await redis_client.setex(
            f"generation:{generation_response.request_id}",
            3600,  # 1 hour
            json.dumps(generation_response.dict())
        )
        
        # Log to ClickHouse for analytics
        clickhouse_client = get_clickhouse()
        try:
            clickhouse_client.execute(
                "INSERT INTO query_metrics VALUES",
                [{
                    'timestamp': datetime.utcnow(),
                    'query_id': generation_request.request_id,
                    'query_text': generation_request.query,
                    'processing_time_ms': generation_response.processing_time_ms,
                    'retrieval_count': len(generation_request.context),
                    'generation_tokens': generation_response.tokens_used,
                    'model_name': generation_response.model_name,
                    'service_name': 'generation-service'
                }]
            )
        except Exception as e:
            logger.warning(f"Failed to log to ClickHouse: {e}")
        
        return generation_response
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List available generation models."""
    model_manager = app.state.model_manager
    models_info = []
    
    for model_name, stats in model_manager.model_usage_stats.items():
        model_info = ModelInfo(
            name=model_name,
            type=ModelType.GENERATION,
            version="1.0.0",
            status="loaded",
            memory_usage_mb=model_manager._get_model_memory_usage(),
            loaded_at=stats["loaded_at"],
            last_used=stats["last_used"],
            config={
                "request_count": stats["request_count"],
                "total_tokens_generated": stats["total_tokens_generated"]
            }
        )
        models_info.append(model_info)
    
    return models_info


@app.post("/models/{model_name}/load")
async def load_model(model_name: str):
    """Load a specific generation model."""
    model_manager = app.state.model_manager
    success = await model_manager.load_model(model_name)
    
    if success:
        return {"message": f"Model {model_name} loaded successfully"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to load model {model_name}")


@app.delete("/models/{model_name}/unload")
async def unload_model(model_name: str):
    """Unload a specific generation model."""
    model_manager = app.state.model_manager
    await model_manager.unload_model(model_name)
    return {"message": f"Model {model_name} unloaded successfully"}


@app.get("/generation/{request_id}", response_model=GenerationResponse)
async def get_generation_result(
    request_id: str,
    redis_client = Depends(get_redis)
):
    """Get cached generation result."""
    # Try cache first
    cached = await redis_client.get(f"generation:{request_id}")
    if cached:
        data = json.loads(cached)
        return GenerationResponse(**data)
    
    # Query database
    db = next(get_db())
    generation = db.query(GenerationHistoryDB).filter(
        GenerationHistoryDB.request_id == request_id
    ).first()
    
    if not generation:
        raise HTTPException(status_code=404, detail="Generation result not found")
    
    return GenerationResponse(
        request_id=generation.request_id,
        response=generation.response,
        model_name=generation.model_name,
        tokens_used=generation.tokens_used,
        processing_time_ms=generation.processing_time_ms,
        metadata={}
    )


@app.get("/generation/history", response_model=List[Dict[str, Any]])
async def get_generation_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get generation history."""
    try:
        generations = db.query(GenerationHistoryDB).order_by(
            GenerationHistoryDB.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return [
            {
                "request_id": gen.request_id,
                "query": gen.query,
                "model_name": gen.model_name,
                "tokens_used": gen.tokens_used,
                "processing_time_ms": gen.processing_time_ms,
                "created_at": gen.created_at
            }
            for gen in generations
        ]
        
    except Exception as e:
        logger.error(f"Get generation history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    model_manager = app.state.model_manager
    llm_manager = app.state.llm_manager
    
    # Check provider health
    provider_health = await llm_manager.health_check()
    
    return {
        "status": "healthy",
        "service": "generation-service",
        "loaded_models": list(model_manager.models.keys()),
        "memory_usage_mb": model_manager._get_model_memory_usage(),
        "providers": llm_manager.list_providers(),
        "provider_health": provider_health
    }


@app.get("/providers")
async def list_providers():
    """List available LLM providers."""
    llm_manager = app.state.llm_manager
    return {
        "providers": llm_manager.list_providers(),
        "default_provider": llm_manager.default_provider
    }


@app.post("/providers/{provider_name}/models/{model_name}/generate")
async def generate_with_provider(
    provider_name: str,
    model_name: str,
    generation_request: GenerationRequest,
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """Generate response using specific provider and model."""
    try:
        llm_manager = app.state.llm_manager
        
        # Override provider and model in request
        if not generation_request.metadata:
            generation_request.metadata = {}
        generation_request.metadata["provider"] = provider_name
        generation_request.model_name = model_name
        
        # Use existing generate endpoint logic
        return await generate_response(generation_request, db, redis_client)
        
    except Exception as e:
        logger.error(f"Provider generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=settings.debug
    )
