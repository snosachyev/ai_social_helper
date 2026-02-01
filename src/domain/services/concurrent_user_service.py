"""Concurrent User Management Service"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import time

logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    user_id: str
    start_time: datetime
    last_activity: datetime
    request_count: int = 0
    active_requests: Set[str] = field(default_factory=set)
    priority: int = 1

class ConcurrentUserService:
    def __init__(self, max_concurrent_users: int = 100):
        self.max_concurrent_users = max_concurrent_users
        self.active_users: Dict[str, UserSession] = {}
        self.user_queue: deque = deque()
        self.request_queue: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.RLock()
        
    async def add_user(self, user_id: str, priority: int = 1) -> bool:
        with self._lock:
            if len(self.active_users) >= self.max_concurrent_users:
                if user_id not in self.active_users:
                    self.user_queue.append((user_id, priority, datetime.now()))
                return False
            
            self.active_users[user_id] = UserSession(
                user_id=user_id,
                start_time=datetime.now(),
                last_activity=datetime.now(),
                priority=priority
            )
            return True
    
    async def remove_user(self, user_id: str):
        with self._lock:
            if user_id in self.active_users:
                del self.active_users[user_id]
                await self._process_queue()
    
    async def _process_queue(self):
        while len(self.active_users) < self.max_concurrent_users and self.user_queue:
            user_id, priority, queue_time = self.user_queue.popleft()
            if self._should_admit_user(user_id, priority, queue_time):
                self.active_users[user_id] = UserSession(
                    user_id=user_id,
                    start_time=datetime.now(),
                    last_activity=datetime.now(),
                    priority=priority
                )
    
    def _should_admit_user(self, user_id: str, priority: int, queue_time: datetime) -> bool:
        wait_time = (datetime.now() - queue_time).total_seconds()
        return wait_time > 30 or priority > 1
    
    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "active_users": len(self.active_users),
                "queued_users": len(self.user_queue),
                "max_concurrent": self.max_concurrent_users,
                "utilization": len(self.active_users) / self.max_concurrent_users
            }
