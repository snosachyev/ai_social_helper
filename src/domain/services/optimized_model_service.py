"""Optimized Model Service with Quantization and Performance Enhancements"""

from typing import List, Dict, Any, Optional, Tuple, Union
import logging
import asyncio
import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, AutoModel, AutoModelForSequenceClassification,
    BitsAndBytesConfig, GPTQConfig, AwqConfig
)
from dataclasses import dataclass
from enum import Enum
import json
import time
from datetime import datetime, timedelta
import psutil
import gc
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, deque
import weakref
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class QuantizationType(Enum):
    """Supported quantization types"""
    NONE = "none"
    BITS_AND_BYTES = "bitsandbytes"
    GPTQ = "gptq"
    AWQ = "awq"
    DYNAMIC = "dynamic"


class ModelShareMode(Enum):
    """Model sharing strategies"""
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    POOLED = "pooled"


@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    public_name: str        # "saiga", "qwen"
    hf_identifier: str       # "IlyaGusev/saiga_mistral_7b"
    model_type: str         # "generation", "classification", "auto"
    quantization: Optional[str] = None  # "4bit", "8bit", None
    max_memory_gb: Optional[float] = None
    required_gpu_memory: Optional[float] = None


@dataclass
class ModelLoadRequest:
    """Request for model loading"""
    model_name: str              # "saiga", "qwen", not HF identifiers
    force_reload: bool = False
    offline_only: Optional[bool] = None  # Uses service default if None


@dataclass
class ModelLoadResponse:
    """Response from model loading"""
    success: bool
    model_name: str
    cache_path: Optional[str] = None
    download_required: bool = False
    error_message: Optional[str] = None
    load_time_ms: Optional[float] = None


@dataclass
class ModelInfo:
    """Information about a model"""
    name: str
    hf_identifier: str
    model_type: str
    quantization: Optional[str]
    is_loaded: bool
    cache_available: bool
    memory_requirements: Dict[str, float]


# Centralized model registry
AVAILABLE_MODELS = {
    "saiga": ModelConfig(
        public_name="saiga",
        hf_identifier="IlyaGusev/saiga_mistral_7b",
        model_type="generation",
        quantization="4bit",
        max_memory_gb=8.0,
        required_gpu_memory=6.0
    ),
    "qwen": ModelConfig(
        public_name="qwen",
        hf_identifier="Qwen/Qwen2.5-7B",
        model_type="generation",
        quantization="4bit",
        max_memory_gb=16.0,
        required_gpu_memory=8.0
    ),
    "embedding": ModelConfig(
        public_name="embedding",
        hf_identifier="sentence-transformers/all-MiniLM-L6-v2",
        model_type="auto",
        quantization=None,
        max_memory_gb=2.0,
        required_gpu_memory=1.0
    )
}


@dataclass
class OptimizationConfig:
    """Configuration for model optimizations"""
    quantization_type: QuantizationType = QuantizationType.BITS_AND_BYTES
    quantization_bits: int = 4
    enable_model_sharing: bool = True
    share_mode: ModelShareMode = ModelShareMode.SHARED
    max_concurrent_users: int = 100
    batch_size: int = 32
    max_batch_wait_time: float = 0.1  # seconds
    enable_kv_cache: bool = True
    max_kv_cache_size: int = 1000
    enable_tensor_parallel: bool = False
    tensor_parallel_size: int = 1
    enable_gradient_checkpointing: bool = True
    enable_cpu_offload: bool = True
    max_memory_gb: float = 16.0
    cache_embeddings: bool = True
    embedding_cache_size: int = 10000
    enable_async_inference: bool = True
    max_queue_size: int = 1000


@dataclass
class BatchRequest:
    """Batch inference request"""
    inputs: List[str]
    request_ids: List[str]
    timestamp: datetime
    priority: int = 1


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    memory_usage_mb: float
    gpu_utilization: float
    inference_time_ms: float
    throughput_qps: float
    cache_hit_rate: float
    queue_size: int
    active_users: int


class OptimizedModelService:
    """High-performance model service with optimizations and registry"""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.model_refs: Dict[str, weakref.ref] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.batch_queue: deque = deque()
        self.inference_executor = ThreadPoolExecutor(max_workers=4)
        self.batch_processor_task = None
        self.embedding_cache: Dict[str, torch.Tensor] = {}
        self.kv_cache: Dict[str, torch.Tensor] = {}
        self.metrics = defaultdict(float)
        self._lock = threading.RLock()
        
        # Registry and cache configuration
        self.model_registry = AVAILABLE_MODELS
        self.loaded_configs: Dict[str, ModelConfig] = {}
        self.offline_mode = os.getenv("HF_OFFLINE_MODE", "true").lower() == "true"
        self.cache_dir = os.getenv("HF_HOME", "~/.cache/huggingface/hub")
        
    async def load_model(self, model_name: str, model_type: str = "auto") -> bool:
        """Legacy method - use load_model_by_name for registry-based loading"""
        logger.warning("load_model is deprecated. Use load_model_by_name with registry validation.")
        return await self._load_legacy_model(model_name, model_type)
    
    async def _load_legacy_model(self, model_name: str, model_type: str = "auto") -> bool:
        """Original model loading logic for backward compatibility"""
        try:
            if model_name in self.models:
                logger.info(f"Model {model_name} already loaded")
                return True
            
            logger.info(f"Loading optimized model: {model_name}")
            
            # Configure quantization
            quantization_config = self._get_quantization_config()
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_fast=True,
                local_files_only=self.offline_mode
            )
            
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Load model with optimizations
            model_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": torch.float16,
                "device_map": "auto",
                "low_cpu_mem_usage": True,
                "local_files_only": self.offline_mode,
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
            
            if self.config.enable_gradient_checkpointing:
                model_kwargs["use_cache"] = not self.config.enable_gradient_checkpointing
            
            # Determine model class based on type
            model_class = self._get_model_class(model_type)
            
            model = model_class.from_pretrained(model_name, **model_kwargs)
            
            # Enable optimizations
            if self.config.enable_kv_cache and hasattr(model, 'config'):
                model.config.use_cache = True
            
            # Optimize model
            model = self._optimize_model(model)
            
            # Store model and tokenizer
            self.models[model_name] = model
            self.tokenizers[model_name] = tokenizer
            
            # Create weak reference for cleanup
            self.model_refs[model_name] = weakref.ref(model)
            
            logger.info(f"Successfully loaded optimized model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    async def load_model_by_name(self, model_name: str, force_reload: bool = False) -> bool:
        """Load model using registry name with validation"""
        
        # Validate model exists in registry
        if model_name not in self.model_registry:
            available = list(self.model_registry.keys())
            logger.error(f"Model '{model_name}' not found. Available: {available}")
            return False
        
        # Check if already loaded
        if model_name in self.models and not force_reload:
            logger.info(f"Model {model_name} already loaded")
            return True
        
        model_config = self.model_registry[model_name]
        
        # Pre-load validation
        if not await self._validate_model_requirements(model_config):
            return False
        
        # Load the model
        success = await self._load_model_from_config(model_config)
        
        if success:
            self.loaded_configs[model_name] = model_config
            logger.info(f"Successfully loaded model: {model_name} ({model_config.hf_identifier})")
        
        return success
    
    async def _validate_model_requirements(self, config: ModelConfig) -> bool:
        """Validate system requirements before loading"""
        
        # Check cache availability
        if self.offline_mode and not self.validate_model_cache(config.hf_identifier):
            logger.error(f"Model {config.hf_identifier} not in cache and offline mode enabled")
            return False
        
        # Check memory requirements
        if config.required_gpu_memory:
            available_gpu_memory = self._get_available_gpu_memory()
            if available_gpu_memory < config.required_gpu_memory:
                logger.error(f"Insufficient GPU memory. Required: {config.required_gpu_memory}GB, Available: {available_gpu_memory}GB")
                return False
        
        # Check system memory
        if config.max_memory_gb:
            available_memory = psutil.virtual_memory().available / (1024**3)
            if available_memory < config.max_memory_gb:
                logger.warning(f"Low system memory. Recommended: {config.max_memory_gb}GB, Available: {available_memory}GB")
        
        return True
    
    async def _load_model_from_config(self, config: ModelConfig) -> bool:
        """Load model using configuration from registry"""
        
        try:
            # Configure quantization based on model config
            quantization_config = None
            if config.quantization:
                quantization_config = self._get_quantization_for_model(config.quantization)
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                config.hf_identifier,
                trust_remote_code=True,
                use_fast=True,
                local_files_only=self.offline_mode
            )
            
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Prepare model loading kwargs
            model_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": torch.float16,
                "device_map": "auto",
                "low_cpu_mem_usage": True,
                "local_files_only": self.offline_mode,
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
            
            if self.config.enable_gradient_checkpointing:
                model_kwargs["use_cache"] = not self.config.enable_gradient_checkpointing
            
            # Get appropriate model class
            model_class = self._get_model_class(config.model_type)
            
            # Load model
            model = model_class.from_pretrained(config.hf_identifier, **model_kwargs)
            
            # Enable optimizations
            if self.config.enable_kv_cache and hasattr(model, 'config'):
                model.config.use_cache = True
            
            # Apply optimizations
            model = self._optimize_model(model)
            
            # Store with registry name as key
            self.models[config.public_name] = model
            self.tokenizers[config.public_name] = tokenizer
            
            # Create weak reference for cleanup
            self.model_refs[config.public_name] = weakref.ref(model)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {config.public_name}: {e}")
            return False
    
    def _get_quantization_for_model(self, quant_type: str) -> Optional[Any]:
        """Get quantization config based on model specification"""
        if quant_type == "4bit":
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        elif quant_type == "8bit":
            return BitsAndBytesConfig(
                load_in_8bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )
        return None
    
    def validate_model_cache(self, model_name: str) -> bool:
        """Check if model exists in HF cache"""
        try:
            from huggingface_hub import snapshot_download
            
            cache_path = snapshot_download(
                repo_id=model_name,
                local_files_only=True,
                cache_dir=self.cache_dir
            )
            return True
        except Exception:
            return False
    
    def _get_available_gpu_memory(self) -> float:
        """Get available GPU memory in GB"""
        try:
            if torch.cuda.is_available():
                total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                allocated_memory = torch.cuda.memory_allocated() / (1024**3)
                return total_memory - allocated_memory
            return 0.0
        except Exception:
            return 0.0
    
    def _get_quantization_config(self) -> Optional[Any]:
        """Get quantization configuration based on type"""
        if self.config.quantization_type == QuantizationType.NONE:
            return None
        
        if self.config.quantization_type == QuantizationType.BITS_AND_BYTES:
            return BitsAndBytesConfig(
                load_in_4bit=self.config.quantization_bits == 4,
                load_in_8bit=self.config.quantization_bits == 8,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        
        elif self.config.quantization_type == QuantizationType.GPTQ:
            return GPTQConfig(
                bits=self.config.quantization_bits,
                group_size=128,
                dataset="c4",
                tokenizer="auto"
            )
        
        elif self.config.quantization_type == QuantizationType.AWQ:
            return AwqConfig(
                bits=self.config.quantization_bits,
                group_size=128,
                zero_point=True
            )
        
        return None
    
    def _get_model_class(self, model_type: str):
        """Get appropriate model class based on type"""
        if model_type == "classification":
            return AutoModelForSequenceClassification
        elif model_type == "generation":
            from transformers import AutoModelForCausalLM
            return AutoModelForCausalLM
        else:
            return AutoModel
    
    def _optimize_model(self, model: nn.Module) -> nn.Module:
        """Apply additional optimizations to loaded model"""
        try:
            # Enable mixed precision
            if hasattr(model, 'half'):
                model = model.half()
            
            # Compile model for better performance (PyTorch 2.0+)
            if hasattr(torch, 'compile'):
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                except Exception as e:
                    logger.warning(f"Model compilation failed: {e}")
            
            # Set model to eval mode
            model.eval()
            
            return model
            
        except Exception as e:
            logger.warning(f"Model optimization failed: {e}")
            return model
    
    async def batch_inference(
        self, 
        model_name: str, 
        inputs: List[str], 
        max_length: int = 512
    ) -> List[torch.Tensor]:
        """Perform batch inference with optimizations"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} not loaded")
            
            model = self.models[model_name]
            tokenizer = self.tokenizers[model_name]
            
            # Batch tokenize
            batch_inputs = tokenizer(
                inputs,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt"
            )
            
            # Move to appropriate device
            device = next(model.parameters()).device
            batch_inputs = {k: v.to(device) for k, v in batch_inputs.items()}
            
            # Batch inference
            with torch.no_grad():
                outputs = model(**batch_inputs)
            
            # Extract embeddings/logits
            if hasattr(outputs, 'last_hidden_state'):
                results = outputs.last_hidden_state
            elif hasattr(outputs, 'logits'):
                results = outputs.logits
            else:
                results = outputs
            
            return results
            
        except Exception as e:
            logger.error(f"Batch inference failed: {e}")
            raise
    
    async def stream_inference(
        self, 
        model_name: str, 
        input_text: str, 
        max_new_tokens: int = 100,
        stream_callback: Optional[callable] = None
    ) -> str:
        """Streaming inference for better user experience"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} not loaded")
            
            model = self.models[model_name]
            tokenizer = self.tokenizers[model_name]
            
            # Tokenize input
            inputs = tokenizer(input_text, return_tensors="pt")
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Generate with streaming
            generated_text = ""
            
            with torch.no_grad():
                for i in range(max_new_tokens):
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=1,
                        do_sample=True,
                        temperature=0.7,
                        pad_token_id=tokenizer.eos_token_id
                    )
                    
                    # Get the new token
                    new_token = tokenizer.decode(outputs[0][-1], skip_special_tokens=True)
                    generated_text += new_token
                    
                    # Call stream callback if provided
                    if stream_callback:
                        await stream_callback(new_token)
                    
                    # Update inputs for next iteration
                    inputs["input_ids"] = outputs
                    inputs["attention_mask"] = torch.ones_like(outputs)
                    
                    # Check for end of sequence
                    if new_token.strip() == "" or tokenizer.eos_token_id in outputs[0]:
                        break
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Stream inference failed: {e}")
            raise
    
    def cache_embeddings(self, key: str, embeddings: torch.Tensor):
        """Cache embeddings for reuse"""
        if not self.config.cache_embeddings:
            return
        
        with self._lock:
            if len(self.embedding_cache) >= self.config.embedding_cache_size:
                # Remove oldest entry (FIFO)
                oldest_key = next(iter(self.embedding_cache))
                del self.embedding_cache[oldest_key]
            
            self.embedding_cache[key] = embeddings.clone().detach()
    
    def get_cached_embeddings(self, key: str) -> Optional[torch.Tensor]:
        """Get cached embeddings"""
        with self._lock:
            return self.embedding_cache.get(key)
    
    async def get_model_metrics(self, model_name: str) -> ModelMetrics:
        """Get comprehensive model performance metrics"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} not loaded")
            
            model = self.models[model_name]
            
            # Memory usage
            if torch.cuda.is_available() and next(model.parameters()).is_cuda:
                gpu_memory = torch.cuda.memory_allocated() / (1024**2)  # MB
                gpu_utilization = self._get_gpu_utilization()
            else:
                gpu_memory = 0
                gpu_utilization = 0
            
            # System memory
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024**2)
            
            # Queue metrics
            queue_size = len(self.batch_queue)
            active_users = len(self.user_sessions)
            
            # Performance metrics
            inference_time = self.metrics.get(f"{model_name}_inference_time", 0)
            throughput = self.metrics.get(f"{model_name}_throughput", 0)
            cache_hit_rate = self.metrics.get(f"{model_name}_cache_hit_rate", 0)
            
            return ModelMetrics(
                memory_usage_mb=memory_mb + gpu_memory,
                gpu_utilization=gpu_utilization,
                inference_time_ms=inference_time,
                throughput_qps=throughput,
                cache_hit_rate=cache_hit_rate,
                queue_size=queue_size,
                active_users=active_users
            )
            
        except Exception as e:
            logger.error(f"Failed to get model metrics: {e}")
            return ModelMetrics(0, 0, 0, 0, 0, 0, 0)
    
    def _get_gpu_utilization(self) -> float:
        """Get current GPU utilization"""
        try:
            if torch.cuda.is_available():
                return torch.cuda.utilization()
            return 0.0
        except:
            return 0.0
    
    async def optimize_memory(self):
        """Optimize memory usage"""
        try:
            # Clear unused models
            for model_name in list(self.models.keys()):
                if model_name not in self.model_refs or self.model_refs[model_name]() is None:
                    del self.models[model_name]
                    if model_name in self.tokenizers:
                        del self.tokenizers[model_name]
            
            # Clear caches if needed
            if len(self.embedding_cache) > self.config.embedding_cache_size * 0.8:
                with self._lock:
                    # Remove 20% of oldest entries
                    items_to_remove = len(self.embedding_cache) // 5
                    for _ in range(items_to_remove):
                        if self.embedding_cache:
                            oldest_key = next(iter(self.embedding_cache))
                            del self.embedding_cache[oldest_key]
            
            # Garbage collection
            gc.collect()
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Memory optimization completed")
            
        except Exception as e:
            logger.error(f"Memory optimization failed: {e}")
    
    async def unload_model(self, model_name: str) -> bool:
        """Unload model and free resources"""
        try:
            if model_name in self.models:
                del self.models[model_name]
            
            if model_name in self.tokenizers:
                del self.tokenizers[model_name]
            
            if model_name in self.model_refs:
                del self.model_refs[model_name]
            
            # Clear related caches
            keys_to_remove = [k for k in self.embedding_cache.keys() if model_name in k]
            with self._lock:
                for key in keys_to_remove:
                    del self.embedding_cache[key]
            
            # Garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"Successfully unloaded model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload model {model_name}: {e}")
            return False
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        return {
            "loaded_models": len(self.models),
            "cached_embeddings": len(self.embedding_cache),
            "kv_cache_size": len(self.kv_cache),
            "active_users": len(self.user_sessions),
            "queue_size": len(self.batch_queue),
            "quantization_type": self.config.quantization_type.value,
            "quantization_bits": self.config.quantization_bits,
            "model_sharing_enabled": self.config.enable_model_sharing,
            "share_mode": self.config.share_mode.value,
            "batch_size": self.config.batch_size,
            "memory_optimization_enabled": True,
            "offline_mode": self.offline_mode,
            "cache_directory": self.cache_dir
        }
    
    async def load_model_endpoint(self, request: ModelLoadRequest) -> ModelLoadResponse:
        """Enhanced endpoint with registry validation"""
        start_time = time.time()
        
        # Validate model exists in registry
        if request.model_name not in self.model_registry:
            available = list(self.model_registry.keys())
            return ModelLoadResponse(
                success=False,
                model_name=request.model_name,
                error_message=f"Model not found. Available: {available}"
            )
        
        # Determine offline mode
        offline_only = request.offline_only if request.offline_only is not None else self.offline_mode
        
        # Check cache availability for offline mode
        if offline_only:
            model_config = self.model_registry[request.model_name]
            if not self.validate_model_cache(model_config.hf_identifier):
                return ModelLoadResponse(
                    success=False,
                    model_name=request.model_name,
                    download_required=True,
                    error_message="Model not in cache and offline_only=True"
                )
        
        # Load model
        success = await self.load_model_by_name(
            request.model_name, 
            force_reload=request.force_reload
        )
        
        load_time = (time.time() - start_time) * 1000
        
        return ModelLoadResponse(
            success=success,
            model_name=request.model_name,
            cache_path=self.get_model_cache_path(self.model_registry[request.model_name].hf_identifier),
            load_time_ms=load_time
        )
    
    def get_model_cache_path(self, model_name: str) -> Optional[str]:
        """Get the actual cache path for a model"""
        try:
            from huggingface_hub import snapshot_download
            return snapshot_download(repo_id=model_name, local_files_only=True, cache_dir=self.cache_dir)
        except Exception:
            return None
    
    def list_cached_models(self) -> List[str]:
        """List all models available in cache"""
        cache_dir = Path(self.cache_dir.replace("~", str(Path.home())))
        if not cache_dir.exists():
            return []
        
        model_dirs = [d for d in cache_dir.iterdir() if d.is_dir() and d.name.startswith("models--")]
        
        # Convert internal names back to public identifiers
        models = []
        for model_dir in model_dirs:
            public_name = model_dir.name.replace("models--", "").replace("--", "/")
            models.append(public_name)
        
        return models
    
    def list_available_models(self) -> List[ModelInfo]:
        """List all available models with their status"""
        models_info = []
        
        for name, config in self.model_registry.items():
            models_info.append(ModelInfo(
                name=name,
                hf_identifier=config.hf_identifier,
                model_type=config.model_type,
                quantization=config.quantization,
                is_loaded=name in self.models,
                cache_available=self.validate_model_cache(config.hf_identifier),
                memory_requirements={
                    "required_gpu": config.required_gpu_memory or 0,
                    "max_system": config.max_memory_gb or 0
                }
            ))
        
        return models_info
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get detailed info about a specific model"""
        if model_name not in self.model_registry:
            return None
        
        config = self.model_registry[model_name]
        return ModelInfo(
            name=model_name,
            hf_identifier=config.hf_identifier,
            model_type=config.model_type,
            quantization=config.quantization,
            is_loaded=model_name in self.models,
            cache_available=self.validate_model_cache(config.hf_identifier),
            memory_requirements={
                "required_gpu": config.required_gpu_memory or 0,
                "max_system": config.max_memory_gb or 0
            }
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Service health including cache status"""
        return {
            "status": "healthy",
            "offline_mode": self.offline_mode,
            "cached_models": len(self.list_cached_models()),
            "available_models": len(self.model_registry),
            "loaded_models": len(self.models),
            "cache_directory": self.cache_dir
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Cleanup resources
        for model_name in list(self.models.keys()):
            await self.unload_model(model_name)
        
        if self.batch_processor_task:
            self.batch_processor_task.cancel()
        
        self.inference_executor.shutdown(wait=True)
