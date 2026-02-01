"""Model Sharing and Caching Service for Resource Optimization"""

from typing import List, Dict, Any, Optional, Set, Tuple
import asyncio
import torch
import threading
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, OrderedDict
import weakref
import psutil
import gc
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ShareMode(Enum):
    """Model sharing modes"""
    EXCLUSIVE = "exclusive"  # One user per model instance
    SHARED = "shared"        # Multiple users share one instance
    POOLED = "pooled"        # Pool of instances for load balancing
    DYNAMIC = "dynamic"      # Adaptive sharing based on load


class CachePolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"              # Least Recently Used
    LFU = "lfu"              # Least Frequently Used
    FIFO = "fifo"            # First In First Out
    TTL = "ttl"              # Time To Live
    ADAPTIVE = "adaptive"    # Adaptive based on usage patterns


@dataclass
class ModelInstance:
    """Represents a single model instance"""
    instance_id: str
    model_name: str
    model: Any
    device: torch.device
    memory_usage_mb: float
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    current_users: Set[str] = field(default_factory=set)
    max_users: int = 10
    share_mode: ShareMode = ShareMode.SHARED
    is_loading: bool = False
    load_lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class CacheConfig:
    """Configuration for model caching"""
    max_memory_gb: float = 8.0
    max_instances: int = 10
    cache_policy: CachePolicy = CachePolicy.LRU
    ttl_minutes: int = 60
    cleanup_interval_minutes: int = 5
    enable_memory_monitoring: bool = True
    enable_usage_tracking: bool = True
    auto_scale_instances: bool = True
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.2


class ModelSharingService:
    """Advanced model sharing and caching service"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.model_instances: Dict[str, ModelInstance] = {}
        self.user_sessions: Dict[str, Set[str]] = defaultdict(set)  # user_id -> instance_ids
        self.usage_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.access_history: OrderedDict = OrderedDict()  # For LRU
        self.frequency_counter: Dict[str, int] = defaultdict(int)  # For LFU
        self._lock = threading.RLock()
        self._cleanup_task = None
        self._monitoring_task = None
        self._shutdown = False
        
        # Memory tracking
        self.total_memory_usage = 0.0
        self.peak_memory_usage = 0.0
        
    async def start(self):
        """Start the sharing service"""
        logger.info("Starting model sharing service")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Start monitoring task if enabled
        if self.config.enable_memory_monitoring:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Model sharing service started")
    
    async def stop(self):
        """Stop the sharing service"""
        logger.info("Stopping model sharing service")
        
        self._shutdown = True
        
        # Cancel tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Wait for tasks to finish
        await asyncio.gather(
            self._cleanup_task, self._monitoring_task,
            return_exceptions=True
        )
        
        # Cleanup all instances
        await self.cleanup_all_instances()
        
        logger.info("Model sharing service stopped")
    
    async def get_model(
        self,
        model_name: str,
        user_id: str,
        share_mode: ShareMode = ShareMode.SHARED,
        force_new_instance: bool = False
    ) -> Optional[str]:
        """Get a model instance for a user"""
        if self._shutdown:
            raise RuntimeError("Service is shutting down")
        
        instance_id = None
        
        with self._lock:
            # Check if user already has access to a suitable instance
            if not force_new_instance and user_id in self.user_sessions:
                user_instances = self.user_sessions[user_id]
                for iid in user_instances:
                    instance = self.model_instances.get(iid)
                    if (instance and instance.model_name == model_name and 
                        len(instance.current_users) < instance.max_users):
                        instance_id = iid
                        break
            
            # Find or create a suitable instance
            if not instance_id:
                instance_id = await self._find_or_create_instance(
                    model_name, user_id, share_mode
                )
            
            if instance_id:
                # Grant user access
                instance = self.model_instances[instance_id]
                instance.current_users.add(user_id)
                instance.last_accessed = datetime.now()
                instance.access_count += 1
                
                self.user_sessions[user_id].add(instance_id)
                
                # Update tracking
                self._update_access_tracking(instance_id)
                self._update_usage_stats(instance_id, user_id)
                
                logger.debug(f"User {user_id} granted access to {instance_id}")
        
        return instance_id
    
    async def _find_or_create_instance(
        self,
        model_name: str,
        user_id: str,
        share_mode: ShareMode
    ) -> Optional[str]:
        """Find existing instance or create new one"""
        # Try to find existing shareable instance
        for instance_id, instance in self.model_instances.items():
            if (instance.model_name == model_name and 
                not instance.is_loading and
                len(instance.current_users) < instance.max_users and
                instance.share_mode in [ShareMode.SHARED, ShareMode.POOLED]):
                
                return instance_id
        
        # Check if we can create a new instance
        if not self._can_create_instance():
            # Try to free up space
            await self._evict_instances()
            if not self._can_create_instance():
                logger.warning("Cannot create new model instance - resource limits reached")
                return None
        
        # Create new instance
        instance_id = await self._create_instance(model_name, share_mode)
        return instance_id
    
    def _can_create_instance(self) -> bool:
        """Check if we can create a new instance"""
        if len(self.model_instances) >= self.config.max_instances:
            return False
        
        if self.total_memory_usage >= self.config.max_memory_gb * 1024:
            return False
        
        return True
    
    async def _create_instance(
        self,
        model_name: str,
        share_mode: ShareMode
    ) -> Optional[str]:
        """Create a new model instance"""
        instance_id = f"{model_name}_{int(time.time())}_{len(self.model_instances)}"
        
        try:
            # Create instance record
            instance = ModelInstance(
                instance_id=instance_id,
                model_name=model_name,
                model=None,  # Will be loaded by model service
                device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
                memory_usage_mb=0.0,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                share_mode=share_mode,
                is_loading=True
            )
            
            self.model_instances[instance_id] = instance
            
            logger.info(f"Created new model instance: {instance_id}")
            return instance_id
            
        except Exception as e:
            logger.error(f"Failed to create instance {instance_id}: {e}")
            return None
    
    def set_model_instance(self, instance_id: str, model: Any, memory_usage_mb: float):
        """Set the actual model for an instance"""
        with self._lock:
            if instance_id in self.model_instances:
                instance = self.model_instances[instance_id]
                instance.model = model
                instance.memory_usage_mb = memory_usage_mb
                instance.is_loading = False
                
                self.total_memory_usage += memory_usage_mb
                self.peak_memory_usage = max(self.peak_memory_usage, self.total_memory_usage)
                
                logger.info(f"Model loaded for instance {instance_id}, memory: {memory_usage_mb:.1f}MB")
    
    async def release_model(self, instance_id: str, user_id: str):
        """Release a user's access to a model instance"""
        with self._lock:
            if instance_id in self.model_instances:
                instance = self.model_instances[instance_id]
                instance.current_users.discard(user_id)
                instance.last_accessed = datetime.now()
                
                # Remove from user sessions
                if user_id in self.user_sessions:
                    self.user_sessions[user_id].discard(instance_id)
                    if not self.user_sessions[user_id]:
                        del self.user_sessions[user_id]
                
                logger.debug(f"User {user_id} released access to {instance_id}")
    
    async def _evict_instances(self):
        """Evict instances based on cache policy"""
        instances_to_evict = []
        
        if self.config.cache_policy == CachePolicy.LRU:
            instances_to_evict = self._evict_lru()
        elif self.config.cache_policy == CachePolicy.LFU:
            instances_to_evict = self._evict_lfu()
        elif self.config.cache_policy == CachePolicy.FIFO:
            instances_to_evict = self._evict_fifo()
        elif self.config.cache_policy == CachePolicy.TTL:
            instances_to_evict = self._evict_ttl()
        elif self.config.cache_policy == CachePolicy.ADAPTIVE:
            instances_to_evict = self._evict_adaptive()
        
        # Evict selected instances
        for instance_id in instances_to_evict:
            await self._remove_instance(instance_id)
    
    def _evict_lru(self) -> List[str]:
        """Evict least recently used instances"""
        # Sort by last accessed time
        sorted_instances = sorted(
            self.model_instances.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Select instances to evict (skip those with active users)
        to_evict = []
        for instance_id, instance in sorted_instances:
            if not instance.current_users and not instance.is_loading:
                to_evict.append(instance_id)
                if len(to_evict) >= 2:  # Evict up to 2 instances
                    break
        
        return to_evict
    
    def _evict_lfu(self) -> List[str]:
        """Evict least frequently used instances"""
        sorted_instances = sorted(
            self.model_instances.items(),
            key=lambda x: x[1].access_count
        )
        
        to_evict = []
        for instance_id, instance in sorted_instances:
            if not instance.current_users and not instance.is_loading:
                to_evict.append(instance_id)
                if len(to_evict) >= 2:
                    break
        
        return to_evict
    
    def _evict_fifo(self) -> List[str]:
        """Evict oldest instances"""
        sorted_instances = sorted(
            self.model_instances.items(),
            key=lambda x: x[1].created_at
        )
        
        to_evict = []
        for instance_id, instance in sorted_instances:
            if not instance.current_users and not instance.is_loading:
                to_evict.append(instance_id)
                if len(to_evict) >= 2:
                    break
        
        return to_evict
    
    def _evict_ttl(self) -> List[str]:
        """Evict instances past TTL"""
        cutoff_time = datetime.now() - timedelta(minutes=self.config.ttl_minutes)
        
        to_evict = []
        for instance_id, instance in self.model_instances.items():
            if (instance.last_accessed < cutoff_time and 
                not instance.current_users and 
                not instance.is_loading):
                to_evict.append(instance_id)
        
        return to_evict
    
    def _evict_adaptive(self) -> List[str]:
        """Adaptive eviction based on multiple factors"""
        # Score instances based on usage, age, and memory
        scored_instances = []
        
        for instance_id, instance in self.model_instances.items():
            if instance.current_users or instance.is_loading:
                continue
            
            # Calculate score (lower is better for eviction)
            time_factor = (datetime.now() - instance.last_accessed).total_seconds() / 3600  # hours
            usage_factor = 1.0 / (instance.access_count + 1)
            memory_factor = instance.memory_usage_mb / 1024  # GB
            
            score = time_factor * 0.4 + usage_factor * 0.4 + memory_factor * 0.2
            scored_instances.append((instance_id, score))
        
        # Sort by score and select top candidates
        scored_instances.sort(key=lambda x: x[1], reverse=True)
        return [instance_id for instance_id, _ in scored_instances[:2]]
    
    async def _remove_instance(self, instance_id: str):
        """Remove a model instance"""
        if instance_id not in self.model_instances:
            return
        
        instance = self.model_instances[instance_id]
        
        # Remove from all user sessions
        for user_id in list(instance.current_users):
            await self.release_model(instance_id, user_id)
        
        # Update memory usage
        self.total_memory_usage -= instance.memory_usage_mb
        
        # Remove instance
        del self.model_instances[instance_id]
        
        # Clear model from GPU if possible
        if instance.model and hasattr(instance.model, 'cpu'):
            try:
                instance.model.cpu()
                del instance.model
            except:
                pass
        
        # Garbage collection
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info(f"Removed model instance: {instance_id}")
    
    def _update_access_tracking(self, instance_id: str):
        """Update access tracking for cache policies"""
        # Update LRU tracking
        if instance_id in self.access_history:
            self.access_history.move_to_end(instance_id)
        else:
            self.access_history[instance_id] = datetime.now()
        
        # Update frequency tracking
        self.frequency_counter[instance_id] += 1
    
    def _update_usage_stats(self, instance_id: str, user_id: str):
        """Update usage statistics"""
        if self.config.enable_usage_tracking:
            now = datetime.now()
            if user_id not in self.usage_stats:
                self.usage_stats[user_id] = {
                    'first_access': now,
                    'last_access': now,
                    'access_count': 0,
                    'instances_used': set()
                }
            
            stats = self.usage_stats[user_id]
            stats['last_access'] = now
            stats['access_count'] += 1
            stats['instances_used'].add(instance_id)
    
    async def _cleanup_loop(self):
        """Periodic cleanup loop"""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)
                
                if not self._shutdown:
                    await self._evict_instances()
                    await self._optimize_memory()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _monitoring_loop(self):
        """Memory monitoring loop"""
        while not self._shutdown:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if not self._shutdown:
                    await self._check_memory_pressure()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    async def _check_memory_pressure(self):
        """Check for memory pressure and take action"""
        if self.total_memory_usage > self.config.max_memory_gb * 1024 * 0.9:
            logger.warning("High memory usage detected, triggering cleanup")
            await self._evict_instances()
    
    async def _optimize_memory(self):
        """Optimize memory usage"""
        # Force garbage collection
        gc.collect()
        
        # Clear CUDA cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    async def cleanup_all_instances(self):
        """Clean up all model instances"""
        with self._lock:
            instance_ids = list(self.model_instances.keys())
        
        for instance_id in instance_ids:
            await self._remove_instance(instance_id)
        
        logger.info("All model instances cleaned up")
    
    def get_sharing_stats(self) -> Dict[str, Any]:
        """Get sharing and caching statistics"""
        with self._lock:
            total_instances = len(self.model_instances)
            active_instances = sum(1 for inst in self.model_instances.values() if inst.current_users)
            total_users = sum(len(inst.current_users) for inst in self.model_instances.values())
            
            return {
                "total_instances": total_instances,
                "active_instances": active_instances,
                "total_active_users": total_users,
                "total_memory_usage_mb": self.total_memory_usage,
                "peak_memory_usage_mb": self.peak_memory_usage,
                "memory_utilization": self.total_memory_usage / (self.config.max_memory_gb * 1024),
                "cache_policy": self.config.cache_policy.value,
                "user_sessions": len(self.user_sessions),
                "average_users_per_instance": total_users / max(total_instances, 1),
                "instances_by_share_mode": self._get_instances_by_mode(),
                "top_users": self._get_top_users()
            }
    
    def _get_instances_by_mode(self) -> Dict[str, int]:
        """Get instance count by share mode"""
        mode_counts = defaultdict(int)
        for instance in self.model_instances.values():
            mode_counts[instance.share_mode.value] += 1
        return dict(mode_counts)
    
    def _get_top_users(self) -> List[Dict[str, Any]]:
        """Get top users by usage"""
        user_stats = []
        for user_id, stats in self.usage_stats.items():
            user_stats.append({
                "user_id": user_id,
                "access_count": stats['access_count'],
                "instances_used": len(stats['instances_used']),
                "last_access": stats['last_access'].isoformat()
            })
        
        return sorted(user_stats, key=lambda x: x['access_count'], reverse=True)[:10]
    
    @contextmanager
    def get_instance_context(self, instance_id: str, user_id: str):
        """Context manager for using a model instance"""
        try:
            yield instance_id
        finally:
            asyncio.create_task(self.release_model(instance_id, user_id))
