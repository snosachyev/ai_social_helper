"""Query domain entities"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

# Import RetrievalResult from embedding module
from .embedding import RetrievalResult


class QueryType(str, Enum):
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    KEYWORD = "keyword"


class ModelType(str, Enum):
    EMBEDDING = "embedding"
    GENERATION = "generation"
    RERANKING = "reranking"


@dataclass
class QueryRequest:
    """Query request entity"""
    query_id: UUID = field(default_factory=uuid4)
    query: str = ""
    query_type: QueryType = QueryType.SEMANTIC
    top_k: int = 5
    filters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.query:
            raise ValueError("Query cannot be empty")
        if self.top_k < 1 or self.top_k > 100:
            raise ValueError("top_k must be between 1 and 100")
    
    def is_hybrid(self) -> bool:
        """Check if this is a hybrid query"""
        return self.query_type == QueryType.HYBRID
    
    def get_model_name(self) -> Optional[str]:
        """Get model name from metadata"""
        return self.metadata.get("model_name")
    
    def add_filter(self, key: str, value: Any) -> None:
        """Add a filter"""
        self.filters[key] = value
    
    def has_filter(self, key: str) -> bool:
        """Check if filter exists"""
        return key in self.filters


@dataclass
class GenerationRequest:
    """Generation request entity"""
    request_id: UUID = field(default_factory=uuid4)
    query: str = ""
    context: List[RetrievalResult] = field(default_factory=list)
    model_name: str = ""
    max_tokens: int = 512
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.query:
            raise ValueError("Query cannot be empty")
        if not self.model_name:
            raise ValueError("Model name is required")
        if self.max_tokens < 1 or self.max_tokens > 4096:
            raise ValueError("max_tokens must be between 1 and 4096")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
    
    def get_context_text(self) -> str:
        """Get concatenated context text"""
        return "\n\n".join(result.text for result in self.context)
    
    def get_context_length(self) -> int:
        """Get total context length"""
        return len(self.get_context_text())


@dataclass
class GenerationResponse:
    """Generation response value object"""
    request_id: UUID
    response: str = ""
    model_name: str = ""
    tokens_used: int = 0
    processing_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.response:
            raise ValueError("Response cannot be empty")
        if self.tokens_used < 0:
            raise ValueError("Tokens used cannot be negative")
        if self.processing_time_ms < 0:
            raise ValueError("Processing time cannot be negative")
    
    def is_successful(self) -> bool:
        """Check if generation was successful"""
        return bool(self.response)
