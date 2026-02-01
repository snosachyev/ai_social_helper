"""Mock repository implementations for testing"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import asyncio
from datetime import datetime

from ...domain.entities.document import Document, TextChunk, DocumentMetadata, ProcessingStatus, DocumentType
from ...domain.entities.embedding import EmbeddingVector, RetrievalResult
from ...domain.repositories.document_repository import DocumentRepository, ChunkRepository
from ...domain.repositories.embedding_repository import EmbeddingRepository, VectorSearchRepository


class MockDocumentRepository(DocumentRepository):
    """Mock document repository for testing"""
    
    def __init__(self):
        self.documents: Dict[UUID, Document] = {}
        self.call_count = 0
        self.last_call_args = {}
    
    async def save(self, document: Document) -> Document:
        self.call_count += 1
        self.last_call_args['save'] = document
        
        self.documents[document.document_id] = document
        return document
    
    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        self.call_count += 1
        self.last_call_args['find_by_id'] = document_id
        
        return self.documents.get(document_id)
    
    async def find_by_filename(self, filename: str) -> Optional[Document]:
        self.call_count += 1
        self.last_call_args['find_by_filename'] = filename
        
        for doc in self.documents.values():
            if doc.metadata.filename == filename:
                return doc
        return None
    
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        self.call_count += 1
        self.last_call_args['find_all'] = {'skip': skip, 'limit': limit}
        
        docs = list(self.documents.values())
        docs.sort(key=lambda x: x.metadata.created_at, reverse=True)
        return docs[skip:skip + limit]
    
    async def find_by_status(self, status: ProcessingStatus) -> List[Document]:
        self.call_count += 1
        self.last_call_args['find_by_status'] = status
        
        return [
            doc for doc in self.documents.values()
            if doc.metadata.status == status
        ]
    
    async def delete(self, document_id: UUID) -> bool:
        self.call_count += 1
        self.last_call_args['delete'] = document_id
        
        if document_id in self.documents:
            del self.documents[document_id]
            return True
        return False
    
    async def update_status(self, document_id: UUID, status: ProcessingStatus) -> bool:
        self.call_count += 1
        self.last_call_args['update_status'] = {'document_id': document_id, 'status': status}
        
        if document_id in self.documents:
            self.documents[document_id].update_status(status)
            return True
        return False
    
    async def get_document_count(self) -> int:
        self.call_count += 1
        self.last_call_args['get_document_count'] = {}
        
        return len(self.documents)
    
    def reset(self):
        """Reset mock state"""
        self.documents.clear()
        self.call_count = 0
        self.last_call_args.clear()


class MockChunkRepository(ChunkRepository):
    """Mock chunk repository for testing"""
    
    def __init__(self):
        self.chunks: Dict[UUID, TextChunk] = {}
        self.call_count = 0
        self.last_call_args = {}
    
    async def save(self, chunk: TextChunk) -> TextChunk:
        self.call_count += 1
        self.last_call_args['save'] = chunk
        
        self.chunks[chunk.chunk_id] = chunk
        return chunk
    
    async def find_by_id(self, chunk_id: UUID) -> Optional[TextChunk]:
        self.call_count += 1
        self.last_call_args['find_by_id'] = chunk_id
        
        return self.chunks.get(chunk_id)
    
    async def find_by_document_id(self, document_id: UUID) -> List[TextChunk]:
        self.call_count += 1
        self.last_call_args['find_by_document_id'] = document_id
        
        return [
            chunk for chunk in self.chunks.values()
            if chunk.document_id == document_id
        ]
    
    async def delete_by_document_id(self, document_id: UUID) -> bool:
        self.call_count += 1
        self.last_call_args['delete_by_document_id'] = document_id
        
        chunks_to_delete = [
            chunk_id for chunk_id, chunk in self.chunks.items()
            if chunk.document_id == document_id
        ]
        
        for chunk_id in chunks_to_delete:
            del self.chunks[chunk_id]
        
        return len(chunks_to_delete) > 0
    
    async def search_text(self, query: str, limit: int = 10) -> List[TextChunk]:
        self.call_count += 1
        self.last_call_args['search_text'] = {'query': query, 'limit': limit}
        
        matching_chunks = [
            chunk for chunk in self.chunks.values()
            if query.lower() in chunk.text.lower()
        ]
        
        return matching_chunks[:limit]
    
    def reset(self):
        """Reset mock state"""
        self.chunks.clear()
        self.call_count = 0
        self.last_call_args.clear()


class MockEmbeddingRepository(EmbeddingRepository):
    """Mock embedding repository for testing"""
    
    def __init__(self):
        self.embeddings: Dict[UUID, EmbeddingVector] = {}
        self.call_count = 0
        self.last_call_args = {}
    
    async def save(self, embedding: EmbeddingVector) -> EmbeddingVector:
        self.call_count += 1
        self.last_call_args['save'] = embedding
        
        self.embeddings[embedding.vector_id] = embedding
        return embedding
    
    async def save_batch(self, embeddings: List[EmbeddingVector]) -> List[EmbeddingVector]:
        self.call_count += 1
        self.last_call_args['save_batch'] = embeddings
        
        for embedding in embeddings:
            self.embeddings[embedding.vector_id] = embedding
        
        return embeddings
    
    async def find_by_id(self, vector_id: UUID) -> Optional[EmbeddingVector]:
        self.call_count += 1
        self.last_call_args['find_by_id'] = vector_id
        
        return self.embeddings.get(vector_id)
    
    async def find_by_chunk_id(self, chunk_id: UUID) -> Optional[EmbeddingVector]:
        self.call_count += 1
        self.last_call_args['find_by_chunk_id'] = chunk_id
        
        for embedding in self.embeddings.values():
            if embedding.chunk_id == chunk_id:
                return embedding
        return None
    
    async def delete(self, vector_id: UUID) -> bool:
        self.call_count += 1
        self.last_call_args['delete'] = vector_id
        
        if vector_id in self.embeddings:
            del self.embeddings[vector_id]
            return True
        return False
    
    async def delete_by_chunk_id(self, chunk_id: UUID) -> bool:
        self.call_count += 1
        self.last_call_args['delete_by_chunk_id'] = chunk_id
        
        embeddings_to_delete = [
            vector_id for vector_id, embedding in self.embeddings.items()
            if embedding.chunk_id == chunk_id
        ]
        
        for vector_id in embeddings_to_delete:
            del self.embeddings[vector_id]
        
        return len(embeddings_to_delete) > 0
    
    async def get_embedding_count(self) -> int:
        self.call_count += 1
        self.last_call_args['get_embedding_count'] = {}
        
        return len(self.embeddings)
    
    def reset(self):
        """Reset mock state"""
        self.embeddings.clear()
        self.call_count = 0
        self.last_call_args.clear()


class MockVectorSearchRepository(VectorSearchRepository):
    """Mock vector search repository for testing"""
    
    def __init__(self):
        self.vectors: Dict[UUID, EmbeddingVector] = {}
        self.search_results: List[RetrievalResult] = []
        self.call_count = 0
        self.last_call_args = {}
        self.similarity_scores: Dict[str, float] = {}
    
    async def search_similar(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[RetrievalResult]:
        self.call_count += 1
        self.last_call_args['search_similar'] = {
            'query_embedding': query_embedding,
            'top_k': top_k,
            'filters': filters
        }
        
        # Return predefined results or generate mock results
        if self.search_results:
            return self.search_results[:top_k]
        
        # Generate mock results based on stored vectors
        results = []
        for i, (vector_id, embedding) in enumerate(list(self.vectors.items())[:top_k]):
            result = RetrievalResult(
                chunk_id=embedding.chunk_id,
                document_id=UUID(),  # Mock document ID
                text=f"Mock text for chunk {embedding.chunk_id}",
                score=self.similarity_scores.get(str(vector_id), 0.8 - i * 0.1),
                metadata={"mock": True}
            )
            results.append(result)
        
        return results
    
    async def add_vectors(self, embeddings: List[EmbeddingVector]) -> bool:
        self.call_count += 1
        self.last_call_args['add_vectors'] = embeddings
        
        for embedding in embeddings:
            self.vectors[embedding.vector_id] = embedding
        
        return True
    
    async def update_vector(self, embedding: EmbeddingVector) -> bool:
        self.call_count += 1
        self.last_call_args['update_vector'] = embedding
        
        self.vectors[embedding.vector_id] = embedding
        return True
    
    async def remove_vector(self, vector_id: UUID) -> bool:
        self.call_count += 1
        self.last_call_args['remove_vector'] = vector_id
        
        if vector_id in self.vectors:
            del self.vectors[vector_id]
            return True
        return False
    
    async def get_index_stats(self) -> Dict[str, Any]:
        self.call_count += 1
        self.last_call_args['get_index_stats'] = {}
        
        return {
            "type": "mock",
            "vector_count": len(self.vectors),
            "dimension": 384,
            "metric": "cosine"
        }
    
    def set_search_results(self, results: List[RetrievalResult]):
        """Set predefined search results"""
        self.search_results = results
    
    def set_similarity_score(self, vector_id: str, score: float):
        """Set similarity score for a vector"""
        self.similarity_scores[vector_id] = score
    
    def reset(self):
        """Reset mock state"""
        self.vectors.clear()
        self.search_results.clear()
        self.similarity_scores.clear()
        self.call_count = 0
        self.last_call_args.clear()
