from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    success: bool = False
    error_code: str
    details: Optional[Dict[str, Any]] = None


class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    HTML = "html"
    MD = "markdown"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelType(str, Enum):
    EMBEDDING = "embedding"
    GENERATION = "generation"
    RERANKING = "reranking"


class QueryType(str, Enum):
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    KEYWORD = "keyword"


class DocumentMetadata(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: DocumentType
    size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingVector(BaseModel):
    vector_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str
    embedding: List[float]
    model_name: str
    dimension: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QueryRequest(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    query_type: QueryType = QueryType.SEMANTIC
    top_k: int = Field(default=5, ge=1, le=100)
    filters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    context: List[RetrievalResult]
    model_name: str
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    request_id: str
    response: str
    model_name: str
    tokens_used: int
    processing_time_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ModelType
    version: str
    status: str
    memory_usage_mb: int
    loaded_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class HealthCheck(BaseModel):
    service_name: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)
