"""SQLAlchemy database models"""

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid


Base = declarative_base()


class DocumentDB(Base):
    """Document database model"""
    __tablename__ = "documents"
    
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False, index=True)
    file_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, nullable=True)


class ChunkDB(Base):
    """Text chunk database model"""
    __tablename__ = "chunks"
    
    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    document = relationship("DocumentDB", backref="chunks")


class EmbeddingDB(Base):
    """Embedding database model"""
    __tablename__ = "embeddings"
    
    vector_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    embedding = Column(Text, nullable=False)  # Store as JSON string
    model_name = Column(String(255), nullable=False)
    dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    chunk = relationship("ChunkDB", backref="embeddings")


class QueryHistoryDB(Base):
    """Query history database model"""
    __tablename__ = "query_history"
    
    query_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True, index=True)
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=False)
    top_k = Column(Integer, nullable=False)
    filters = Column(JSON, nullable=True)
    results_count = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    guard_allowed = Column(Boolean, nullable=False)
    guard_risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class GenerationHistoryDB(Base):
    """Generation history database model"""
    __tablename__ = "generation_history"
    
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True, index=True)
    query = Column(Text, nullable=False)
    context_length = Column(Integer, nullable=False)
    model_name = Column(String(255), nullable=False)
    max_tokens = Column(Integer, nullable=False)
    temperature = Column(Float, nullable=False)
    response = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    guard_allowed = Column(Boolean, nullable=False)
    guard_risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class VectorMetadataDB(Base):
    """Vector metadata database model"""
    __tablename__ = "vector_metadata"
    
    vector_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    text = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModelMetricsDB(Base):
    """Model metrics database model"""
    __tablename__ = "model_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    model_name = Column(String(255), nullable=False)
    model_type = Column(String(50), nullable=False)
    memory_usage_mb = Column(Integer, nullable=False)
    request_count = Column(Integer, nullable=False)
    avg_processing_time_ms = Column(Float, nullable=False)


class QueryMetricsDB(Base):
    """Query metrics database model"""
    __tablename__ = "query_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    query_id = Column(UUID(as_uuid=True), nullable=False)
    query_text = Column(Text, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    retrieval_count = Column(Integer, nullable=False)
    generation_tokens = Column(Integer, nullable=False)
    model_name = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False)


class DocumentMetricsDB(Base):
    """Document metrics database model"""
    __tablename__ = "document_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    file_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    chunk_count = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)


# Import relationship
from sqlalchemy.orm import relationship
