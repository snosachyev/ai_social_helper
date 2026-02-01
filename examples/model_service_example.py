#!/usr/bin/env python3
"""
Example usage of the Enhanced OptimizedModelService with model registry
"""

import asyncio
import logging
from src.domain.services.optimized_model_service import (
    OptimizedModelService,
    OptimizationConfig,
    ModelLoadRequest,
    QuantizationType,
    ModelShareMode
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Demonstrate enhanced model service usage"""
    
    # Create optimization configuration
    config = OptimizationConfig(
        quantization_type=QuantizationType.BITS_AND_BYTES,
        quantization_bits=4,
        enable_model_sharing=True,
        share_mode=ModelShareMode.SHARED,
        max_concurrent_users=10,
        batch_size=16,
        enable_kv_cache=True,
        enable_gradient_checkpointing=True,
        enable_cpu_offload=True,
        max_memory_gb=16.0
    )
    
    # Initialize the enhanced model service
    service = OptimizedModelService(config)
    
    try:
        # Example 1: List available models
        logger.info("=== Available Models ===")
        available_models = service.list_available_models()
        for model_info in available_models:
            status = "✓ Loaded" if model_info.is_loaded else "✗ Not loaded"
            cache_status = "✓ Cached" if model_info.cache_available else "✗ Not cached"
            logger.info(f"{model_info.name}: {status} | {cache_status}")
            logger.info(f"  HF ID: {model_info.hf_identifier}")
            logger.info(f"  Type: {model_info.model_type} | Quantization: {model_info.quantization}")
            logger.info(f"  Memory: GPU {model_info.memory_requirements['required_gpu']}GB, System {model_info.memory_requirements['max_system']}GB")
            logger.info("")
        
        # Example 2: Load a model using registry name
        logger.info("=== Loading Model ===")
        success = await service.load_model_by_name("embedding")
        if success:
            logger.info("✓ Embedding model loaded successfully")
        else:
            logger.error("✗ Failed to load embedding model")
        
        # Example 3: Use the enhanced API endpoint
        logger.info("=== Using API Endpoint ===")
        request = ModelLoadRequest(
            model_name="saiga",
            force_reload=False,
            offline_only=True
        )
        
        response = await service.load_model_endpoint(request)
        if response.success:
            logger.info(f"✓ Model loaded in {response.load_time_ms:.2f}ms")
            logger.info(f"  Cache path: {response.cache_path}")
        else:
            logger.error(f"✗ Failed to load model: {response.error_message}")
            if response.download_required:
                logger.info("  Download required - model not in cache")
        
        # Example 4: Get specific model info
        logger.info("=== Model Information ===")
        saiga_info = service.get_model_info("saiga")
        if saiga_info:
            logger.info(f"SAIGA Model Info:")
            logger.info(f"  Loaded: {saiga_info.is_loaded}")
            logger.info(f"  Cached: {saiga_info.cache_available}")
            logger.info(f"  HF Identifier: {saiga_info.hf_identifier}")
        
        # Example 5: Health check
        logger.info("=== Service Health ===")
        health = await service.health_check()
        logger.info(f"Service Status: {health['status']}")
        logger.info(f"Offline Mode: {health['offline_mode']}")
        logger.info(f"Cached Models: {health['cached_models']}")
        logger.info(f"Loaded Models: {health['loaded_models']}")
        logger.info(f"Cache Directory: {health['cache_directory']}")
        
        # Example 6: List cached models
        logger.info("=== Cached Models ===")
        cached_models = service.list_cached_models()
        logger.info(f"Models in cache: {cached_models}")
        
        # Example 7: Get optimization stats
        logger.info("=== Optimization Stats ===")
        stats = service.get_optimization_stats()
        logger.info(f"Loaded models: {stats['loaded_models']}")
        logger.info(f"Offline mode: {stats['offline_mode']}")
        logger.info(f"Cache directory: {stats['cache_directory']}")
        
    finally:
        # Cleanup
        await service.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
