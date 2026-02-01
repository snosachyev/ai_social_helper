"""Performance Integration Service"""

from typing import Dict, Any, Optional
import asyncio
import logging
from ..domain.services.optimized_model_service import OptimizedModelService, OptimizationConfig, QuantizationType, ModelShareMode
from ..domain.services.batch_inference_service import BatchInferenceService, BatchConfig
from ..domain.services.model_sharing_service import ModelSharingService, CacheConfig, ShareMode, CachePolicy
from ..domain.services.concurrent_user_service import ConcurrentUserService

logger = logging.getLogger(__name__)

class PerformanceService:
    """Integrated performance optimization service"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_service: Optional[OptimizedModelService] = None
        self.batch_service: Optional[BatchInferenceService] = None
        self.sharing_service: Optional[ModelSharingService] = None
        self.user_service: Optional[ConcurrentUserService] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all performance services"""
        if self._initialized:
            return
        
        logger.info("Initializing performance services")
        
        # Initialize model service
        model_config = OptimizationConfig(
            quantization_type=QuantizationType(
                self.config.get("quantization", {}).get("type", "bitsandbytes")
            ),
            quantization_bits=self.config.get("quantization", {}).get("bits", 4),
            enable_model_sharing=self.config.get("model_sharing", {}).get("enabled", True),
            share_mode=ModelShareMode(
                self.config.get("model_sharing", {}).get("mode", "shared")
            ),
            max_concurrent_users=self.config.get("concurrent_users", {}).get("max_concurrent", 100),
            batch_size=self.config.get("batch_inference", {}).get("max_batch_size", 32),
            max_batch_wait_time=self.config.get("batch_inference", {}).get("max_wait_time", 0.1),
            enable_kv_cache=self.config.get("memory_optimization", {}).get("enable_kv_cache", True),
            max_kv_cache_size=self.config.get("memory_optimization", {}).get("max_kv_cache_size", 1000),
            enable_gradient_checkpointing=self.config.get("memory_optimization", {}).get("enable_gradient_checkpointing", True),
            enable_cpu_offload=self.config.get("memory_optimization", {}).get("enable_cpu_offload", True),
            max_memory_gb=self.config.get("max_memory_gb", 16.0),
            cache_embeddings=self.config.get("caching", {}).get("enable_embeddings_cache", True),
            embedding_cache_size=self.config.get("caching", {}).get("embeddings_cache_size", 10000),
            enable_async_inference=True
        )
        
        self.model_service = OptimizedModelService(model_config)
        
        # Initialize batch service
        batch_config = BatchConfig(
            max_batch_size=self.config.get("batch_inference", {}).get("max_batch_size", 32),
            max_wait_time=self.config.get("batch_inference", {}).get("max_wait_time", 0.1),
            priority_levels=self.config.get("batch_inference", {}).get("priority_levels", 3),
            enable_adaptive_batching=self.config.get("batch_inference", {}).get("adaptive_batching", True),
            max_concurrent_batches=4
        )
        
        self.batch_service = BatchInferenceService(batch_config)
        self.batch_service.set_model_service(self.model_service)
        
        # Initialize sharing service
        sharing_config = CacheConfig(
            max_memory_gb=self.config.get("max_memory_gb", 8.0),
            max_instances=self.config.get("model_sharing", {}).get("max_instances", 10),
            cache_policy=CachePolicy(
                self.config.get("model_sharing", {}).get("cache_policy", "lru")
            ),
            ttl_minutes=self.config.get("model_sharing", {}).get("ttl_minutes", 60),
            cleanup_interval_minutes=self.config.get("memory_optimization", {}).get("cleanup_interval_minutes", 5),
            enable_memory_monitoring=True,
            enable_usage_tracking=True,
            auto_scale_instances=True
        )
        
        self.sharing_service = ModelSharingService(sharing_config)
        await self.sharing_service.start()
        
        # Initialize user service
        self.user_service = ConcurrentUserService(
            max_concurrent_users=self.config.get("concurrent_users", {}).get("max_concurrent", 100)
        )
        
        self._initialized = True
        logger.info("Performance services initialized successfully")
    
    async def shutdown(self):
        """Shutdown all performance services"""
        if not self._initialized:
            return
        
        logger.info("Shutting down performance services")
        
        if self.sharing_service:
            await self.sharing_service.stop()
        
        if self.batch_service:
            await self.batch_service.shutdown()
        
        if self.model_service:
            await self.model_service.optimize_memory()
        
        self._initialized = False
        logger.info("Performance services shutdown complete")
    
    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        if not self._initialized:
            return {"error": "Performance services not initialized"}
        
        metrics = {
            "model_service": {},
            "batch_service": {},
            "sharing_service": {},
            "user_service": {}
        }
        
        # Model service metrics
        if self.model_service and self.model_service.models:
            model_name = list(self.model_service.models.keys())[0]
            model_metrics = await self.model_service.get_model_metrics(model_name)
            metrics["model_service"] = {
                "memory_usage_mb": model_metrics.memory_usage_mb,
                "gpu_utilization": model_metrics.gpu_utilization,
                "inference_time_ms": model_metrics.inference_time_ms,
                "throughput_qps": model_metrics.throughput_qps,
                "cache_hit_rate": model_metrics.cache_hit_rate,
                "queue_size": model_metrics.queue_size,
                "active_users": model_metrics.active_users
            }
        
        # Batch service metrics
        if self.batch_service:
            metrics["batch_service"] = {
                "queue_stats": self.batch_service.get_queue_stats(),
                "performance_metrics": self.batch_service.get_performance_metrics()
            }
        
        # Sharing service metrics
        if self.sharing_service:
            metrics["sharing_service"] = self.sharing_service.get_sharing_stats()
        
        # User service metrics
        if self.user_service:
            metrics["user_service"] = self.user_service.get_stats()
        
        return metrics
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization configuration summary"""
        return {
            "quantization": {
                "enabled": self.config.get("quantization", {}).get("enabled", False),
                "type": self.config.get("quantization", {}).get("type", "none"),
                "bits": self.config.get("quantization", {}).get("bits", 4)
            },
            "model_sharing": {
                "enabled": self.config.get("model_sharing", {}).get("enabled", False),
                "mode": self.config.get("model_sharing", {}).get("mode", "exclusive"),
                "max_instances": self.config.get("model_sharing", {}).get("max_instances", 1)
            },
            "batch_inference": {
                "enabled": self.config.get("batch_inference", {}).get("enabled", False),
                "max_batch_size": self.config.get("batch_inference", {}).get("max_batch_size", 1),
                "max_wait_time": self.config.get("batch_inference", {}).get("max_wait_time", 0.1)
            },
            "concurrent_users": {
                "max_concurrent": self.config.get("concurrent_users", {}).get("max_concurrent", 1),
                "queue_timeout": self.config.get("concurrent_users", {}).get("queue_timeout", 30)
            },
            "memory_optimization": {
                "enable_kv_cache": self.config.get("memory_optimization", {}).get("enable_kv_cache", False),
                "enable_cpu_offload": self.config.get("memory_optimization", {}).get("enable_cpu_offload", False),
                "enable_gradient_checkpointing": self.config.get("memory_optimization", {}).get("enable_gradient_checkpointing", False)
            },
            "caching": {
                "enable_embeddings_cache": self.config.get("caching", {}).get("enable_embeddings_cache", False),
                "embeddings_cache_size": self.config.get("caching", {}).get("embeddings_cache_size", 0),
                "enable_results_cache": self.config.get("caching", {}).get("enable_results_cache", False)
            }
        }
