"""Mock tracer for testing"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio

from ...infrastructure.tracing.phoenix_tracer import TracingProvider, SpanData


class MockTracer(TracingProvider):
    """Mock tracer for testing"""
    
    def __init__(self):
        self.spans: Dict[str, SpanData] = {}
        self.call_count = 0
        self.last_call_args = {}
        self.span_counter = 0
        self.trace_counter = 0
        self.start_span_delay = 0.0
        self.end_span_delay = 0.0
        self.should_fail = False
        self.failure_message = "Mock tracer operation failed"
    
    async def start_span(self, operation_name: str, parent_span: Optional[str] = None) -> str:
        self.call_count += 1
        self.last_call_args['start_span'] = {'operation_name': operation_name, 'parent_span': parent_span}
        
        if self.start_span_delay > 0:
            await asyncio.sleep(self.start_span_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Generate unique span ID
        span_id = f"mock-span-{self.span_counter}"
        self.span_counter += 1
        
        # Generate trace ID (reuse parent's trace ID or create new)
        trace_id = None
        if parent_span and parent_span in self.spans:
            trace_id = self.spans[parent_span].trace_id
        else:
            trace_id = f"mock-trace-{self.trace_counter}"
            self.trace_counter += 1
        
        # Create span data
        span_data = SpanData(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span,
            operation_name=operation_name,
            start_time=datetime.utcnow()
        )
        
        self.spans[span_id] = span_data
        return span_id
    
    async def end_span(self, span_id: str, status: str = "ok", status_message: str = ""):
        self.call_count += 1
        self.last_call_args['end_span'] = {'span_id': span_id, 'status': status, 'status_message': status_message}
        
        if self.end_span_delay > 0:
            await asyncio.sleep(self.end_span_delay)
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        if span_id in self.spans:
            self.spans[span_id].end_time = datetime.utcnow()
            self.spans[span_id].status = status
            self.spans[span_id].status_message = status_message
    
    async def add_attribute(self, span_id: str, key: str, value: Any):
        self.call_count += 1
        self.last_call_args['add_attribute'] = {'span_id': span_id, 'key': key, 'value': value}
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        if span_id in self.spans:
            self.spans[span_id].attributes[key] = value
    
    async def add_event(self, span_id: str, event_name: str, attributes: Dict[str, Any] = None):
        self.call_count += 1
        self.last_call_args['add_event'] = {'span_id': span_id, 'event_name': event_name, 'attributes': attributes}
        
        if self.should_fail:
            raise Exception(self.failure_message)
        
        if span_id in self.spans:
            event = {
                "name": event_name,
                "timestamp": datetime.utcnow().isoformat(),
                "attributes": attributes or {}
            }
            self.spans[span_id].events.append(event)
    
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
    
    def get_span(self, span_id: str) -> Optional[SpanData]:
        """Get span data by ID"""
        return self.spans.get(span_id)
    
    def get_spans_by_trace(self, trace_id: str) -> List[SpanData]:
        """Get all spans for a trace"""
        return [span for span in self.spans.values() if span.trace_id == trace_id]
    
    def get_all_spans(self) -> List[SpanData]:
        """Get all spans"""
        return list(self.spans.values())
    
    def get_active_spans(self) -> List[SpanData]:
        """Get active spans (those without end_time)"""
        return [span for span in self.spans.values() if span.end_time is None]
    
    def set_start_span_delay(self, delay: float):
        """Set delay for start span operation"""
        self.start_span_delay = delay
    
    def set_end_span_delay(self, delay: float):
        """Set delay for end span operation"""
        self.end_span_delay = delay
    
    def set_failure(self, should_fail: bool, message: str = "Mock tracer operation failed"):
        """Set whether to simulate failure"""
        self.should_fail = should_fail
        self.failure_message = message
    
    def reset(self):
        """Reset mock state"""
        self.spans.clear()
        self.call_count = 0
        self.last_call_args.clear()
        self.span_counter = 0
        self.trace_counter = 0
        self.start_span_delay = 0.0
        self.end_span_delay = 0.0
        self.should_fail = False


class MockTracingService:
    """Mock tracing service for testing"""
    
    def __init__(self, tracer: MockTracer):
        self.tracer = tracer
        self.call_count = 0
        self.last_call_args = {}
    
    @asynccontextmanager
    async def trace_query(self, query_request):
        """Trace a query operation"""
        self.call_count += 1
        self.last_call_args['trace_query'] = query_request
        
        async with self.tracer.trace("query.process") as span_id:
            await self.tracer.add_attribute(span_id, "query.id", str(query_request.query_id))
            await self.tracer.add_attribute(span_id, "query.text", query_request.query)
            await self.tracer.add_attribute(span_id, "query.type", query_request.query_type.value)
            await self.tracer.add_attribute(span_id, "query.top_k", query_request.top_k)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_embedding_generation(self, text: str, model_name: str):
        """Trace embedding generation"""
        self.call_count += 1
        self.last_call_args['trace_embedding_generation'] = {'text': text, 'model_name': model_name}
        
        async with self.tracer.trace("embedding.generate") as span_id:
            await self.tracer.add_attribute(span_id, "embedding.model", model_name)
            await self.tracer.add_attribute(span_id, "embedding.text_length", len(text))
            
            yield span_id
    
    @asynccontextmanager
    async def trace_vector_search(self, query_embedding, top_k: int):
        """Trace vector search"""
        self.call_count += 1
        self.last_call_args['trace_vector_search'] = {'query_embedding': query_embedding, 'top_k': top_k}
        
        async with self.tracer.trace("vector.search") as span_id:
            await self.tracer.add_attribute(span_id, "search.model", query_embedding.model_name)
            await self.tracer.add_attribute(span_id, "search.dimension", query_embedding.dimension)
            await self.tracer.add_attribute(span_id, "search.top_k", top_k)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_reranking(self, query: str, result_count: int):
        """Trace reranking"""
        self.call_count += 1
        self.last_call_args['trace_reranking'] = {'query': query, 'result_count': result_count}
        
        async with self.tracer.trace("reranking.process") as span_id:
            await self.tracer.add_attribute(span_id, "reranking.query_length", len(query))
            await self.tracer.add_attribute(span_id, "reranking.result_count", result_count)
            
            yield span_id
    
    @asynccontextmanager
    async def trace_generation(self, generation_request):
        """Trace text generation"""
        self.call_count += 1
        self.last_call_args['trace_generation'] = generation_request
        
        async with self.tracer.trace("generation.process") as span_id:
            await self.tracer.add_attribute(span_id, "generation.id", str(generation_request.request_id))
            await self.tracer.add_attribute(span_id, "generation.model", generation_request.model_name)
            await self.tracer.add_attribute(span_id, "generation.max_tokens", generation_request.max_tokens)
            await self.tracer.add_attribute(span_id, "generation.temperature", generation_request.temperature)
            await self.tracer.add_attribute(span_id, "generation.context_length", len(generation_request.context))
            
            yield span_id
    
    async def trace_guard_validation(self, operation: str, guard_result):
        """Trace guard validation"""
        self.call_count += 1
        self.last_call_args['trace_guard_validation'] = {'operation': operation, 'guard_result': guard_result}
        
        async with self.tracer.trace(f"guard.{operation}") as span_id:
            await self.tracer.add_attribute(span_id, "guard.allowed", guard_result.is_allowed)
            await self.tracer.add_attribute(span_id, "guard.risk_score", guard_result.risk_score)
            await self.tracer.add_attribute(span_id, "guard.reason", guard_result.reason)
            
            return span_id
    
    def reset(self):
        """Reset mock state"""
        self.call_count = 0
        self.last_call_args.clear()
