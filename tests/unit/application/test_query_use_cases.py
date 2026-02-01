"""Unit tests for query use cases"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from shared.models.base import (
    QueryRequest, RetrievalResult, GenerationRequest, QueryType
)
from src.application.use_cases.query_use_case import (
    QueryUseCase, QueryResponse, GenerationResponseData
)
from src.domain.services.guard_service import Guard, GuardResult
from src.domain.repositories.embedding_repository import EmbeddingRepository
from src.domain.repositories.vector_repository import VectorRepository


class TestQueryUseCase:
    """Test QueryUseCase"""
    
    @pytest.fixture
    def mock_embedding_repository(self):
        """Mock embedding repository"""
        return Mock(spec=EmbeddingRepository)
    
    @pytest.fixture
    def mock_vector_repository(self):
        """Mock vector repository"""
        return Mock(spec=VectorRepository)
    
    @pytest.fixture
    def mock_guard_service(self):
        """Mock guard service"""
        return Mock(spec=Guard)
    
    @pytest.fixture
    def query_use_case(self, mock_embedding_repository, mock_vector_repository, mock_guard_service):
        """Query use case with mocked dependencies"""
        return QueryUseCase(
            embedding_repository=mock_embedding_repository,
            vector_repository=mock_vector_repository,
            guard_service=mock_guard_service
        )
    
    @pytest.fixture
    def sample_query_request(self):
        """Sample query request"""
        return QueryRequest(
            query="What is machine learning?",
            query_type=QueryType.SEMANTIC,
            top_k=5,
            filters={"document_type": "pdf"},
            metadata={"user_id": "test_user"}
        )
    
    @pytest.fixture
    def sample_retrieval_results(self):
        """Sample retrieval results"""
        return [
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="Machine learning is a subset of artificial intelligence",
                score=0.95,
                metadata={"source": "textbook"}
            ),
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="ML algorithms use statistical techniques to learn patterns",
                score=0.87,
                metadata={"source": "research_paper"}
            ),
            RetrievalResult(
                chunk_id=str(uuid4()),
                document_id=str(uuid4()),
                text="Deep learning is a type of machine learning",
                score=0.82,
                metadata={"source": "blog_post"}
            )
        ]
    
    @pytest.fixture
    def safe_guard_result(self):
        """Safe guard result"""
        return GuardResult(
            is_allowed=True,
            reason="Query is safe",
            risk_score=0.1,
            metadata={"category": "educational"}
        )
    
    @pytest.fixture
    def unsafe_guard_result(self):
        """Unsafe guard result"""
        return GuardResult(
            is_allowed=False,
            reason="Query contains harmful content",
            risk_score=0.9,
            metadata={"category": "harmful"}
        )
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self, query_use_case, mock_embedding_repository, 
                                       mock_vector_repository, mock_guard_service,
                                       sample_query_request, sample_retrieval_results, safe_guard_result):
        """Test successful query execution"""
        # Arrange
        query_embedding = [0.1, 0.2, 0.3] * 128  # 384-dimensional embedding
        
        mock_guard_service.check_query.return_value = safe_guard_result
        mock_embedding_repository.get_embedding.return_value = query_embedding
        mock_vector_repository.similarity_search.return_value = sample_retrieval_results
        
        # Act
        result = await query_use_case.execute_query(sample_query_request)
        
        # Assert
        assert result is not None
        assert isinstance(result, QueryResponse)
        assert result.query_id == sample_query_request.query_id
        assert len(result.results) == 3
        assert result.processing_time_ms > 0
        assert result.guard_result == safe_guard_result
        
        # Check retrieval results
        assert result.results[0].text == "Machine learning is a subset of artificial intelligence"
        assert result.results[0].score == 0.95
        assert result.results[1].score == 0.87
        assert result.results[2].score == 0.82
        
        # Verify interactions
        mock_guard_service.check_query.assert_called_once_with(sample_query_request.query)
        mock_embedding_repository.get_embedding.assert_called_once_with(
            sample_query_request.query, model_name=None
        )
        mock_vector_repository.similarity_search.assert_called_once_with(
            query_embedding, top_k=5, filters={"document_type": "pdf"}
        )
    
    @pytest.mark.asyncio
    async def test_execute_query_unsafe_content(self, query_use_case, mock_guard_service,
                                               mock_embedding_repository, mock_vector_repository,
                                               sample_query_request, unsafe_guard_result):
        """Test query execution with unsafe content"""
        # Arrange
        mock_guard_service.check_query.return_value = unsafe_guard_result
        
        # Act
        result = await query_use_case.execute_query(sample_query_request)
        
        # Assert
        assert result is not None
        assert result.guard_result == unsafe_guard_result
        assert result.guard_result.is_allowed is False
        assert len(result.results) == 0  # No results for unsafe queries
        
        # Verify guard was called but no further processing
        mock_guard_service.check_query.assert_called_once_with(sample_query_request.query)
        mock_embedding_repository.get_embedding.assert_not_called()
        mock_vector_repository.similarity_search.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_query_no_results(self, query_use_case, mock_embedding_repository,
                                          mock_vector_repository, mock_guard_service,
                                          sample_query_request, safe_guard_result):
        """Test query execution with no results"""
        # Arrange
        query_embedding = [0.1, 0.2, 0.3] * 128
        
        mock_guard_service.check_query.return_value = safe_guard_result
        mock_embedding_repository.get_embedding.return_value = query_embedding
        mock_vector_repository.similarity_search.return_value = []
        
        # Act
        result = await query_use_case.execute_query(sample_query_request)
        
        # Assert
        assert result is not None
        assert len(result.results) == 0
        assert result.guard_result == safe_guard_result
        
        mock_vector_repository.similarity_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_query_embedding_error(self, query_use_case, mock_guard_service,
                                               mock_embedding_repository, sample_query_request, safe_guard_result):
        """Test query execution with embedding generation error"""
        # Arrange
        mock_guard_service.check_query.return_value = safe_guard_result
        mock_embedding_repository.get_embedding.side_effect = Exception("Model loading failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Model loading failed"):
            await query_use_case.execute_query(sample_query_request)
    
    @pytest.mark.asyncio
    async def test_execute_query_vector_search_error(self, query_use_case, mock_embedding_repository,
                                                    mock_vector_repository, mock_guard_service,
                                                    sample_query_request, safe_guard_result):
        """Test query execution with vector search error"""
        # Arrange
        query_embedding = [0.1, 0.2, 0.3] * 128
        
        mock_guard_service.check_query.return_value = safe_guard_result
        mock_embedding_repository.get_embedding.return_value = query_embedding
        mock_vector_repository.similarity_search.side_effect = Exception("Vector database connection failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Vector database connection failed"):
            await query_use_case.execute_query(sample_query_request)
    
    @pytest.mark.asyncio
    async def test_execute_query_different_query_types(self, query_use_case, mock_embedding_repository,
                                                       mock_vector_repository, mock_guard_service,
                                                       safe_guard_result):
        """Test query execution with different query types"""
        # Test HYBRID query
        hybrid_request = QueryRequest(
            query="test query",
            query_type=QueryType.HYBRID,
            top_k=3
        )
        
        query_embedding = [0.1, 0.2, 0.3] * 128
        
        mock_guard_service.check_query.return_value = safe_guard_result
        mock_embedding_repository.get_embedding.return_value = query_embedding
        mock_vector_repository.similarity_search.return_value = []
        
        await query_use_case.execute_query(hybrid_request)
        
        # Verify hybrid query was processed
        mock_vector_repository.similarity_search.assert_called_with(
            query_embedding, top_k=3, filters={}
        )
        
        # Reset mocks
        mock_vector_repository.reset_mock()
        
        # Test KEYWORD query
        keyword_request = QueryRequest(
            query="test query",
            query_type=QueryType.KEYWORD,
            top_k=10
        )
        
        await query_use_case.execute_query(keyword_request)
        
        # Verify keyword query was processed
        mock_vector_repository.similarity_search.assert_called_with(
            query_embedding, top_k=10, filters={}
        )
    
    @pytest.mark.asyncio
    async def test_execute_generation_success(self, query_use_case, mock_guard_service,
                                            sample_query_request, sample_retrieval_results, safe_guard_result):
        """Test successful generation execution"""
        # Arrange
        generation_request = GenerationRequest(
            query="Summarize machine learning",
            context=sample_retrieval_results,
            model_name="gpt-3.5-turbo",
            max_tokens=256,
            temperature=0.7
        )
        
        expected_response = "Machine learning is a field of AI that focuses on algorithms..."
        
        mock_guard_service.check_generation.return_value = safe_guard_result
        
        # Mock the generation method
        with patch.object(query_use_case, '_generate_response', return_value=expected_response) as mock_generate:
            # Act
            result = await query_use_case.execute_generation(generation_request)
            
            # Assert
            assert result is not None
            assert isinstance(result, GenerationResponseData)
            assert result.request_id == generation_request.request_id
            assert result.response == expected_response
            assert result.model_name == "gpt-3.5-turbo"
            assert result.tokens_used > 0
            assert result.processing_time_ms > 0
            assert result.guard_result == safe_guard_result
            
            # Verify interactions
            mock_guard_service.check_generation.assert_called_once_with(
                generation_request.query, generation_request.context
            )
            mock_generate.assert_called_once_with(generation_request)
    
    @pytest.mark.asyncio
    async def test_execute_generation_unsafe_content(self, query_use_case, mock_guard_service,
                                                    sample_query_request, sample_retrieval_results, unsafe_guard_result):
        """Test generation execution with unsafe content"""
        # Arrange
        generation_request = GenerationRequest(
            query="Generate harmful content",
            context=sample_retrieval_results
        )
        
        mock_guard_service.check_generation.return_value = unsafe_guard_result
        
        # Act
        result = await query_use_case.execute_generation(generation_request)
        
        # Assert
        assert result is not None
        assert result.guard_result == unsafe_guard_result
        assert result.guard_result.is_allowed is False
        assert result.response == ""  # Empty response for unsafe content
        
        # Verify guard was called but no generation
        mock_guard_service.check_generation.assert_called_once_with(
            generation_request.query, generation_request.context
        )
    
    @pytest.mark.asyncio
    async def test_execute_generation_empty_context(self, query_use_case, mock_guard_service,
                                                   sample_query_request, safe_guard_result):
        """Test generation execution with empty context"""
        # Arrange
        generation_request = GenerationRequest(
            query="Generate without context",
            context=[]
        )
        
        expected_response = "Generated response without context"
        
        mock_guard_service.check_generation.return_value = safe_guard_result
        
        with patch.object(query_use_case, '_generate_response', return_value=expected_response):
            # Act
            result = await query_use_case.execute_generation(generation_request)
            
            # Assert
            assert result is not None
            assert result.response == expected_response
            
            mock_guard_service.check_generation.assert_called_once_with(
                generation_request.query, []
            )
    
    @pytest.mark.asyncio
    async def test_get_query_suggestions(self, query_use_case, mock_vector_repository):
        """Test getting query suggestions"""
        # Arrange
        partial_query = "machine le"
        expected_suggestions = ["machine learning", "machine learning algorithms", "machine learning models"]
        
        mock_vector_repository.get_query_suggestions.return_value = expected_suggestions
        
        # Act
        result = await query_use_case.get_query_suggestions(partial_query)
        
        # Assert
        assert result == expected_suggestions
        mock_vector_repository.get_query_suggestions.assert_called_once_with(partial_query)
    
    @pytest.mark.asyncio
    async def test_get_query_history(self, query_use_case, mock_vector_repository):
        """Test getting query history"""
        # Arrange
        user_id = "test_user"
        expected_history = [
            {"query": "what is AI", "timestamp": "2024-01-01T10:00:00"},
            {"query": "machine learning basics", "timestamp": "2024-01-01T09:30:00"}
        ]
        
        mock_vector_repository.get_query_history.return_value = expected_history
        
        # Act
        result = await query_use_case.get_query_history(user_id)
        
        # Assert
        assert result == expected_history
        mock_vector_repository.get_query_history.assert_called_once_with(user_id)
