"""Smoke tests for authentication service"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from src.presentation.api.app import create_application


class TestAuthBasic:
    """Basic authentication tests"""
    
    def test_auth_health_endpoint(self):
        """Test auth health endpoint"""
        app = create_application()
        client = TestClient(app)
        
        response = client.get("/auth/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "auth-service"
    
    def test_user_registration_basic(self):
        """Test basic user registration"""
        # Create mocks
        mock_auth_use_case = Mock()
        mock_auth_use_case.register_user = AsyncMock()
        
        # Mock response
        from src.domain.entities.user import UserResponse
        mock_response = UserResponse(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            role="user",
            status="active",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            last_login=None,
            user_metadata={}
        )
        mock_auth_use_case.register_user.return_value = mock_response
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.auth_controller import get_auth_use_case
        
        app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
        
        # Create client and test
        client = TestClient(app)
        
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "securepassword123",
            "full_name": "Test User"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == mock_response.email
        assert data["username"] == mock_response.username
        assert data["full_name"] == mock_response.full_name
        
        # Verify mock was called
        mock_auth_use_case.register_user.assert_called_once()
    
    def test_user_login_basic(self):
        """Test basic user login"""
        # Create mocks
        mock_auth_use_case = Mock()
        mock_auth_use_case.login_user = AsyncMock()
        mock_tracing_service = Mock()
        mock_tracing_service.trace_operation = Mock()
        mock_tracing_service.trace_operation.return_value.__aenter__ = AsyncMock()
        mock_tracing_service.trace_operation.return_value.__aexit__ = AsyncMock()
        
        # Mock response
        from src.domain.entities.user import Token
        mock_response = Token(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            token_type="bearer",
            expires_in=1800,
            refresh_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        )
        mock_auth_use_case.login_user.return_value = mock_response
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.auth_controller import get_auth_use_case, get_tracing_service
        
        app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
        app.dependency_overrides[get_tracing_service] = lambda: mock_tracing_service
        
        # Create client and test
        client = TestClient(app)
        
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == mock_response.access_token
        assert data["token_type"] == mock_response.token_type
        assert data["expires_in"] == mock_response.expires_in
        assert "refresh_token" in data
        
        # Verify mock was called
        mock_auth_use_case.login_user.assert_called_once()
    
    def test_get_current_user_basic(self):
        """Test getting current user info"""
        # Create mocks
        mock_auth_use_case = Mock()
        mock_auth_use_case.get_current_user = AsyncMock()
        
        # Mock response
        from src.domain.entities.user import UserResponse
        mock_response = UserResponse(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            role="user",
            status="active",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            last_login="2024-01-01T12:00:00",
            user_metadata={}
        )
        mock_auth_use_case.get_current_user.return_value = mock_response
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.auth_controller import get_auth_use_case, get_current_user
        
        app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
        app.dependency_overrides[get_current_user] = lambda: mock_response
        
        # Create client and test
        client = TestClient(app)
        
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer mock_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_response.email
        assert data["username"] == mock_response.username
        assert data["role"] == mock_response.role
        
        # Verify mock was called
        mock_auth_use_case.get_current_user.assert_called_once()


class TestAuthErrorHandling:
    """Test authentication error handling"""
    
    def test_invalid_login_credentials(self):
        """Test login with invalid credentials"""
        # Create mocks
        mock_auth_use_case = Mock()
        mock_auth_use_case.login_user = AsyncMock()
        mock_auth_use_case.login_user.side_effect = ValueError("Invalid credentials")
        mock_tracing_service = Mock()
        mock_tracing_service.trace_operation = Mock()
        mock_tracing_service.trace_operation.return_value.__aenter__ = AsyncMock()
        mock_tracing_service.trace_operation.return_value.__aexit__ = AsyncMock()
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.auth_controller import get_auth_use_case, get_tracing_service
        
        app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
        app.dependency_overrides[get_tracing_service] = lambda: mock_tracing_service
        
        # Create client and test
        client = TestClient(app)
        
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Invalid credentials"
    
    def test_duplicate_email_registration(self):
        """Test registration with duplicate email"""
        # Create mocks
        mock_auth_use_case = Mock()
        mock_auth_use_case.register_user = AsyncMock()
        mock_auth_use_case.register_user.side_effect = ValueError("Email already registered")
        mock_tracing_service = Mock()
        mock_tracing_service.trace_operation = Mock()
        mock_tracing_service.trace_operation.return_value.__aenter__ = AsyncMock()
        mock_tracing_service.trace_operation.return_value.__aexit__ = AsyncMock()
        
        # Create app and override dependencies
        app = create_application()
        
        # Import the actual dependency functions
        from src.presentation.api.auth_controller import get_auth_use_case, get_tracing_service
        
        app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_use_case
        app.dependency_overrides[get_tracing_service] = lambda: mock_tracing_service
        
        # Create client and test
        client = TestClient(app)
        
        user_data = {
            "email": "existing@example.com",
            "username": "newuser",
            "password": "securepassword123"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Email already registered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
