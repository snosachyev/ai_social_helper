"""Embedding domain entities"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4


@dataclass
class EmbeddingVector:
    """Embedding vector value object"""
    vector_id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    embedding: List[float] = field(default_factory=list)
    model_name: str = ""
    dimension: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.embedding:
            raise ValueError("Embedding cannot be empty")
        if self.dimension != len(self.embedding):
            self.dimension = len(self.embedding)
        if not self.model_name:
            raise ValueError("Model name is required")
    
    def get_magnitude(self) -> float:
        """Calculate vector magnitude"""
        return sum(x**2 for x in self.embedding) ** 0.5
    
    def normalize(self) -> "EmbeddingVector":
        """Return normalized copy of the vector"""
        magnitude = self.get_magnitude()
        if magnitude == 0:
            raise ValueError("Cannot normalize zero vector")
        
        normalized_embedding = [x / magnitude for x in self.embedding]
        return EmbeddingVector(
            vector_id=self.vector_id,
            chunk_id=self.chunk_id,
            embedding=normalized_embedding,
            model_name=self.model_name,
            dimension=self.dimension,
            created_at=self.created_at
        )
    
    def cosine_similarity(self, other: "EmbeddingVector") -> float:
        """Calculate cosine similarity with another vector"""
        if self.dimension != other.dimension:
            raise ValueError("Vectors must have same dimension")
        
        dot_product = sum(a * b for a, b in zip(self.embedding, other.embedding))
        magnitude_a = self.get_magnitude()
        magnitude_b = other.get_magnitude()
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)


@dataclass
class RetrievalResult:
    """Retrieval result value object"""
    chunk_id: UUID
    document_id: UUID
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not 0 <= self.score <= 1:
            raise ValueError("Score must be between 0 and 1")
        if not self.text:
            raise ValueError("Text cannot be empty")
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if result is high confidence"""
        return self.score >= threshold
