"""Phoenix tracing integration"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ContextManager
from dataclasses import dataclass, field
import logging
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio
import json

try:
    from phoenix.trace.tracer import Tracer
    from phoenix.trace.exporter import HttpExporter
    from phoenix.trace.attributes import SpanKind
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    Tracer = None
    HttpExporter = None
    SpanKind = None

from ...domain.entities.query import QueryRequest, GenerationRequest
from ...domain.entities.embedding import EmbeddingVector


logger = logging.getLogger(__name__)


@dataclass
class SpanData:
    """Span data for tracing"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"
    status_message: str = ""


class TracingProvider(ABC):
    """Abstract tracing provider"""
    
    @abstractmethod
    async def start_span(self, operation_name: str, parent_span: Optional[str] = None) -> str:
        """Start a new span"""
        pass
    
    @abstractmethod
    async def end_span(self, span_id: str, status: str = "ok", status_message: str = ""):
        """End a span"""
        pass
    
    @abstractmethod
    async def add_attribute(self, span_id: str, key: str, value: Any):
        """Add attribute to span"""
        pass
    
    @abstractmethod
    async def add_event(self, span_id: str, event_name: str, attributes: Dict[str, Any] = None):
        """Add event to span"""
        pass
    
    @asynccontextmanager
    async def trace(self, operation_name: str, parent_span: Optional[str] = None):
        """Context manager for tracing"""
        span_id = await self.start_span(operation_name, parent_span)
        try:
            yield span_id
        except Exception as e:
            await self.end_span(span_id, "error", str(e))
            raise
        else:
            await self.end_span(span_id)


class PhoenixTracer(TracingProvider):
    """Phoenix tracing implementation"""
    
    def __init__(self, endpoint: str = "http://localhost:6006/v1/traces"):
        if not PHOENIX_AVAILABLE:
            raise ImportError("Phoenix is not installed. Install with: pip install arize-phoenix")
        
        self.endpoint = endpoint
        self.tracer = None
        self.exporter = None
        self._initialized = False
        self._active_spans: Dict[str, SpanData] = {}
    
    async def initialize(self):
        """Initialize Phoenix tracer"""
        if self._initialized:
            return
        
        try:
            # Create exporter
            self.exporter = HttpExporter(endpoint=self.endpoint)
            
            # Create tracer
            self.tracer = Tracer(exporter=self.exporter)
            
            self._initialized = True
            logger.info(f"Phoenix tracer initialized with endpoint: {self.endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Phoenix tracer: {e}")
            raise TracingError(f"Failed to initialize Phoenix tracer: {str(e)}")
    
    async def start_span(self, operation_name: str, parent_span: Optional[str] = None) -> str:
        """Start a new span"""
        await self.initialize()
        
        try:
            # Create span data
            span_data = SpanData(
                span_id=self._generate_span_id(),
                trace_id=self._generate_trace_id(),
                parent_span_id=parent_span,
                operation_name=operation_name
            )
            
            # Store active span
            self._active_spans[span_data.span_id] = span_data
            
            # Start Phoenix span
            phoenix_span = self.tracer.start_span(
                operation_name=operation_name,
                kind=SpanKind.INTERNAL,
                trace_id=span_data.trace_id,
                span_id=span_data.span_id
            )
            
            if parent_span:
                phoenix_span.set_parent_span_id(parent_span)
            
            # Store Phoenix span reference
            span_data.attributes["_phoenix_span"] = phoenix_span
            
            logger.debug(f"Started span: {operation_name} ({span_data.span_id})")
            return span_data.span_id
            
        except Exception as e:
            logger.error(f"Failed to start span: {e}")
            raise TracingError(f"Failed to start span: {str(e)}")
    
    async def end_span(self, span_id: str, status: str = "ok", status_message: str = ""):
        """End a span"""
        try:
            if span_id not in self._active_spans:
                logger.warning(f"Span not found: {span_id}")
                return
            
            span_data = self._active_spans[span_id]
            span_data.end_time = datetime.utcnow()
            span_data.status = status
            span_data.status_message = status_message
            
            # End Phoenix span
            phoenix_span = span_data.attributes.get("_phoenix_span")
            if phoenix_span:
                phoenix_span.set_status(status, status_message)
                phoenix_span.end()
            
            # Remove from active spans
            del self._active_spans[span_id]
            
            logger.debug(f"Ended span: {span_data.operation_name} ({span_id})")
            
        except Exception as e:
            logger.error(f"Failed to end span: {e}")
            raise TracingError(f"Failed to end span: {str(e)}")
    
    async def add_attribute(self, span_id: str, key: str, value: Any):
        """Add attribute to span"""
        try:
            if span_id not in self._active_spans:
                logger.warning(f"Span not found: {span_id}")
                return
            
            span_data = self._active_spans[span_id]
            span_data.attributes[key] = value
            
            # Add to Phoenix span
            phoenix_span = span_data.attributes.get("_phoenix_span")
            if phoenix_span:
                phoenix_span.set_attribute(key, str(value))
            
            logger.debug(f"Added attribute to span {span_id}: {key}={value}")
            
        except Exception as e:
            logger.error(f"Failed to add attribute: {e}")
    
    async def add_event(self, span_id: str, event_name: str, attributes: Dict[str, Any] = None):
        """Add event to span"""
        try:
            if span_id not in self._active_spans:
                logger.warning(f"Span not found: {span_id}")
                return
            
            span_data = self._active_spans[span_id]
            event = {
                "name": event_name,
                "timestamp": datetime.utcnow().isoformat(),
                "attributes": attributes or {}
            }
            span_data.events.append(event)
            
            # Add to Phoenix span
            phoenix_span = span_data.attributes.get("_phoenix_span")
            if phoenix_span:
                phoenix_span.add_event(event_name, attributes or {})
            
            logger.debug(f"Added event to span {span_id}: {event_name}")
            
        except Exception as e:
            logger.error(f"Failed to add event: {e}")
    
    def _generate_span_id(self) -> str:
        """Generate a unique span ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID"""
        import uuid
        return str(uuid.uuid4())
    
    async def get_active_spans(self) -> List[SpanData]:
        """Get all active spans"""
        return list(self._active_spans.values())
    
    async def cleanup(self):
        """Cleanup tracer"""
        # End all active spans
        for span_id in list(self._active_spans.keys()):
            await self.end_span(span_id, "cancelled", "Tracer cleanup")
        
        logger.info("Phoenix tracer cleaned up")


class NoOpTracer(TracingProvider):
    """No-op tracer for when tracing is disabled"""
    
    async def start_span(self, operation_name: str, parent_span: Optional[str] = None) -> str:
        return f"noop-span-{id(self)}"
    
    async def end_span(self, span_id: str, status: str = "ok", status_message: str = ""):
        pass
    
    async def add_attribute(self, span_id: str, key: str, value: Any):
        pass
    
    async def add_event(self, span_id: str, event_name: str, attributes: Dict[str, Any] = None):
        pass


class TracingService:
    """High-level tracing service for RAG operations"""
    
    def __init__(self, tracer: TracingProvider):
        self.tracer = tracer
    
    @asynccontextmanager
    async def trace_query(self, query_request: QueryRequest):
        """Trace a query operation"""
        async with self.tracer.trace("query.process") as span_id:
            await self.tracer.add_attribute(span_id, "query.id", str(query_request.query_id))
            await self.tracer.add_attribute(span_id, "query.text", query_request.query)
            await self.tracer.add_attribute(span_id, "query.type", query_request.query_type.value)
            await self.tracer.add_attribute(span_id, "query.top_k", query_request.top_k)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_embedding_generation(self, text: str, model_name: str):
        """Trace embedding generation"""
        async with self.tracer.trace("embedding.generate") as span_id:
            await self.tracer.add_attribute(span_id, "embedding.model", model_name)
            await self.tracer.add_attribute(span_id, "embedding.text_length", len(text))
            
            yield span_id
    
    @asynccontextmanager
    async def trace_vector_search(self, query_embedding: EmbeddingVector, top_k: int):
        """Trace vector search"""
        async with self.tracer.trace("vector.search") as span_id:
            await self.tracer.add_attribute(span_id, "search.model", query_embedding.model_name)
            await self.tracer.add_attribute(span_id, "search.dimension", query_embedding.dimension)
            await self.tracer.add_attribute(span_id, "search.top_k", top_k)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_reranking(self, query: str, result_count: int):
        """Trace reranking"""
        async with self.tracer.trace("reranking.process") as span_id:
            await self.tracer.add_attribute(span_id, "reranking.query_length", len(query))
            await self.tracer.add_attribute(span_id, "reranking.result_count", result_count)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_generation(self, generation_request: GenerationRequest):
        """Trace text generation"""
        async with self.tracer.trace("generation.process") as span_id:
            await self.tracer.add_attribute(span_id, "generation.id", str(generation_request.request_id))
            await self.tracer.add_attribute(span_id, "generation.model", generation_request.model_name)
            await self.tracer.add_attribute(span_id, "generation.max_tokens", generation_request.max_tokens)
            await self.tracer.add_attribute(span_id, "generation.temperature", generation_request.temperature)
            await self.tracer.add_attribute(span_id, "generation.context_length", len(generation_request.context))
            
            yield span_id
    
    async def trace_guard_validation(self, operation: str, guard_result: "GuardResult"):
        """Trace guard validation"""
        async with self.tracer.trace(f"guard.{operation}") as span_id:
            await self.tracer.add_attribute(span_id, "guard.allowed", guard_result.is_allowed)
            await self.tracer.add_attribute(span_id, "guard.risk_score", guard_result.risk_score)
            await self.tracer.add_attribute(span_id, "guard.reason", guard_result.reason)
            
            return span_id


class TracingError(Exception):
    """Tracing related errors"""
    pass


# Factory function
async def create_tracer(config: dict) -> TracingProvider:
    """Create tracer based on configuration"""
    if not config.get("enable_tracing", False):
        return NoOpTracer()
    
    backend = config.get("tracing_backend", "phoenix")
    
    if backend == "phoenix":
        endpoint = config.get("tracing_endpoint", "http://localhost:6006/v1/traces")
        return PhoenixTracer(endpoint)
    else:
        return NoOpTracer()
