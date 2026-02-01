"""Batch Inference Service for High-Throughput Processing"""

from typing import List, Dict, Any, Optional, Callable, Union
import asyncio
import torch
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import asynccontextmanager
import uuid
import weakref

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """Individual request in a batch"""
    request_id: str
    input_text: str
    timestamp: datetime
    priority: int = 1
    max_length: int = 512
    future: asyncio.Future = field(default_factory=lambda: asyncio.Future())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    max_batch_size: int = 32
    max_wait_time: float = 0.1  # seconds
    priority_levels: int = 3
    enable_adaptive_batching: bool = True
    adaptive_threshold: float = 0.8
    enable_batch_splitting: bool = True
    max_sequence_length: int = 512
    enable_padding_optimization: bool = True
    enable_dynamic_batching: bool = True
    batch_timeout: float = 5.0
    max_concurrent_batches: int = 4


class BatchInferenceService:
    """High-performance batch inference service"""
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self.request_queues: Dict[int, deque] = defaultdict(deque)
        self.batch_executor = ThreadPoolExecutor(max_workers=4)
        self.processing = False
        self.metrics = defaultdict(list)
        self.model_service = None
        self._lock = threading.RLock()
        self._shutdown = False
        
        # Performance tracking
        self.total_requests = 0
        self.total_batches = 0
        self.total_processing_time = 0
        self.cache_hits = 0
        
    def set_model_service(self, model_service):
        """Set the model service for inference"""
        self.model_service = model_service
    
    async def submit_request(
        self,
        input_text: str,
        priority: int = 1,
        max_length: int = 512,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a request for batch processing"""
        if self._shutdown:
            raise RuntimeError("Batch service is shutting down")
        
        request_id = str(uuid.uuid4())
        request = BatchRequest(
            request_id=request_id,
            input_text=input_text,
            timestamp=datetime.now(),
            priority=min(max(priority, 1), self.config.priority_levels),
            max_length=max_length,
            metadata=metadata or {}
        )
        
        # Add to appropriate priority queue
        with self._lock:
            self.request_queues[request.priority].append(request)
            self.total_requests += 1
        
        # Start batch processor if not running
        if not self.processing:
            asyncio.create_task(self._batch_processor())
        
        return request_id
    
    async def get_result(self, request_id: str, timeout: float = 30.0) -> Any:
        """Get result for a specific request"""
        # Find the request
        request = None
        for queue in self.request_queues.values():
            for req in queue:
                if req.request_id == request_id:
                    request = req
                    break
            if request:
                break
        
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        try:
            return await asyncio.wait_for(request.future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {request_id} timed out")
    
    async def _batch_processor(self):
        """Main batch processing loop"""
        if self.processing:
            return
        
        self.processing = True
        logger.info("Batch processor started")
        
        try:
            while not self._shutdown:
                batch = await self._collect_batch()
                if batch:
                    asyncio.create_task(self._process_batch(batch))
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
        except Exception as e:
            logger.error(f"Batch processor error: {e}")
        finally:
            self.processing = False
            logger.info("Batch processor stopped")
    
    async def _collect_batch(self) -> Optional[List[BatchRequest]]:
        """Collect requests into a batch"""
        batch = []
        start_time = time.time()
        
        while (len(batch) < self.config.max_batch_size and 
               time.time() - start_time < self.config.max_wait_time):
            
            # Check queues by priority (higher priority first)
            for priority in sorted(self.request_queues.keys(), reverse=True):
                queue = self.request_queues[priority]
                
                while queue and len(batch) < self.config.max_batch_size:
                    with self._lock:
                        if queue:
                            batch.append(queue.popleft())
                    
                    if self.config.enable_adaptive_batching:
                        # Check if we should wait for more high-priority requests
                        if (len(batch) >= self.config.max_batch_size * self.config.adaptive_threshold and
                            priority == max(self.request_queues.keys())):
                            break
            
            if batch:
                break
            
            await asyncio.sleep(0.001)  # Very short sleep
        
        return batch if batch else None
    
    async def _process_batch(self, batch: List[BatchRequest]):
        """Process a batch of requests"""
        if not batch or not self.model_service:
            return
        
        batch_start_time = time.time()
        batch_id = str(uuid.uuid4())[:8]
        
        try:
            logger.debug(f"Processing batch {batch_id} with {len(batch)} requests")
            
            # Prepare batch inputs
            texts = [req.input_text for req in batch]
            max_length = max(req.max_length for req in batch)
            
            # Check for cached results
            cached_results = {}
            uncached_requests = []
            
            for i, req in enumerate(batch):
                cache_key = f"{hash(req.input_text)}_{req.max_length}"
                cached_result = self.model_service.get_cached_embeddings(cache_key)
                if cached_result is not None:
                    cached_results[i] = cached_result
                    self.cache_hits += 1
                else:
                    uncached_requests.append((i, req))
            
            # Process uncached requests
            if uncached_requests:
                uncached_texts = [req.input_text for _, req in uncached_requests]
                uncached_indices = [i for i, _ in uncached_requests]
                
                # Perform batch inference
                results = await self.model_service.batch_inference(
                    model_name=list(self.model_service.models.keys())[0],  # Use first available model
                    inputs=uncached_texts,
                    max_length=max_length
                )
                
                # Cache results and assign to requests
                for idx, (i, req) in enumerate(uncached_requests):
                    if idx < len(results):
                        result = results[idx]
                        cache_key = f"{hash(req.input_text)}_{req.max_length}"
                        self.model_service.cache_embeddings(cache_key, result)
                        cached_results[i] = result
            
            # Set results for all requests
            for i, req in enumerate(batch):
                if i in cached_results:
                    req.future.set_result(cached_results[i])
                else:
                    req.future.set_exception(
                        RuntimeError(f"No result available for request {req.request_id}")
                    )
            
            # Update metrics
            batch_time = time.time() - batch_start_time
            self.total_batches += 1
            self.total_processing_time += batch_time
            
            # Record batch metrics
            self.metrics['batch_times'].append(batch_time)
            self.metrics['batch_sizes'].append(len(batch))
            self.metrics['throughput'].append(len(batch) / batch_time)
            
            logger.debug(f"Batch {batch_id} completed in {batch_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Set exception for all requests in batch
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)
    
    async def submit_batch(
        self,
        inputs: List[str],
        priority: int = 1,
        max_length: int = 512,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Submit a batch of requests together"""
        request_ids = []
        
        for input_text in inputs:
            request_id = await self.submit_request(
                input_text=input_text,
                priority=priority,
                max_length=max_length,
                metadata=metadata
            )
            request_ids.append(request_id)
        
        return request_ids
    
    async def get_batch_results(
        self,
        request_ids: List[str],
        timeout: float = 30.0
    ) -> List[Any]:
        """Get results for a batch of requests"""
        tasks = [self.get_result(req_id, timeout) for req_id in request_ids]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self._lock:
            queue_sizes = {priority: len(queue) for priority, queue in self.request_queues.items()}
            total_queued = sum(queue_sizes.values())
            
            return {
                "queue_sizes": queue_sizes,
                "total_queued": total_queued,
                "total_requests": self.total_requests,
                "total_batches": self.total_batches,
                "cache_hits": self.cache_hits,
                "cache_hit_rate": self.cache_hits / max(self.total_requests, 1),
                "average_batch_time": self.total_processing_time / max(self.total_batches, 1),
                "processing": self.processing
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        if not self.metrics['batch_times']:
            return {}
        
        batch_times = self.metrics['batch_times']
        batch_sizes = self.metrics['batch_sizes']
        throughputs = self.metrics['throughput']
        
        return {
            "average_batch_time": sum(batch_times) / len(batch_times),
            "max_batch_time": max(batch_times),
            "min_batch_time": min(batch_times),
            "average_batch_size": sum(batch_sizes) / len(batch_sizes),
            "max_batch_size": max(batch_sizes),
            "average_throughput": sum(throughputs) / len(throughputs),
            "max_throughput": max(throughputs),
            "total_processed_requests": sum(batch_sizes),
            "total_batches_processed": len(batch_times)
        }
    
    async def clear_queues(self):
        """Clear all request queues"""
        with self._lock:
            for queue in self.request_queues.values():
                # Cancel all pending requests
                for req in queue:
                    if not req.future.done():
                        req.future.cancel()
                queue.clear()
        
        logger.info("All request queues cleared")
    
    async def shutdown(self):
        """Shutdown the batch service gracefully"""
        logger.info("Shutting down batch inference service")
        
        self._shutdown = True
        
        # Clear queues
        await self.clear_queues()
        
        # Wait for current processing to finish
        if self.processing:
            await asyncio.sleep(0.1)
        
        # Shutdown executor
        self.batch_executor.shutdown(wait=True)
        
        logger.info("Batch inference service shutdown complete")
    
    @asynccontextmanager
    async def batch_context(self):
        """Context manager for batch processing"""
        try:
            yield self
        finally:
            await self.shutdown()
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'batch_executor'):
            self.batch_executor.shutdown(wait=False)
