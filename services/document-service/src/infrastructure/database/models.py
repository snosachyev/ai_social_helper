from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from shared.utils.database import Base


class DocumentDB(Base):
    """SQLAlchemy model for Document entity."""
    __tablename__ = "documents"
    
    document_id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    document_metadata = Column(JSON)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ChunkDB(Base):
    """SQLAlchemy model for TextChunk entity."""
    __tablename__ = "chunks"
    
    chunk_id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON)
