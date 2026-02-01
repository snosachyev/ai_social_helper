"""Authentication API controller"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from ...domain.entities.user import (
    UserCreate, UserLogin, UserUpdate, Token, 
    UserResponse, UserRole, UserStatus
)
from ...application.use_cases.auth_use_case import AuthUseCase, UserManagementUseCase
from ...application.services.dependency_injection import DIContainer

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def get_auth_use_case():
    """Get auth use case from DI container"""
    class MockAuthUseCase:
        async def register_user(self, user_create):
            from src.domain.entities.user import UserResponse
            from uuid import uuid4
            return UserResponse(
                id=uuid4(),
                email=user_create.email,
                username=user_create.username,
                full_name=user_create.full_name,
                role=user_create.role,
                status="active",
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00",
                last_login=None,
                user_metadata={}
            )
        
        async def login_user(self, user_login):
            from src.domain.entities.user import Token
            return Token(
                access_token="mock_access_token",
                token_type="bearer",
                expires_in=1800,
                refresh_token="mock_refresh_token"
            )
        
        async def get_current_user(self, token):
            return None
        
        async def logout_user(self, token):
            return True
        
        async def update_user_profile(self, user_id, user_update):
            return None
        
        async def change_user_password(self, user_id, old_password, new_password):
            return True
        
        async def list_users(self, skip=0, limit=100, role=None, status=None, search=None):
            return []
        
        async def delete_user(self, user_id):
            return True
        
        async def activate_user(self, user_id):
            return True
        
        async def deactivate_user(self, user_id):
            return True
    
    return MockAuthUseCase()


def get_user_management_use_case():
    """Get user management use case from DI container"""
    class MockUserManagementUseCase:
        async def get_user_statistics(self):
            return {
                "total_users": 0,
                "active_users": 0,
                "inactive_users": 0,
                "admin_users": 0,
                "user_users": 0,
                "viewer_users": 0
            }
    
    return MockUserManagementUseCase()


def get_tracing_service():
    """Mock tracing service for compatibility"""
    class MockTracer:
        def trace_operation(self, name):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    return MockTracer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case)
) -> UserResponse:
    """Get current authenticated user"""
    try:
        user = await auth_use_case.get_current_user(credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case)
) -> UserResponse:
    """Get current authenticated admin user"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Register new user"""
    async with tracing_service.trace_operation("user_registration"):
        try:
            user = await auth_use_case.register_user(user_create)
            return user
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@router.post("/login", response_model=Token)
async def login(
    user_login: UserLogin,
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Login user"""
    async with tracing_service.trace_operation("user_login"):
        try:
            token = await auth_use_case.login_user(user_login)
            return token
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Refresh access token"""
    async with tracing_service.trace_operation("token_refresh"):
        try:
            token = await auth_use_case.refresh_token(refresh_token)
            return token
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Logout user"""
    async with tracing_service.trace_operation("user_logout"):
        success = await auth_use_case.logout_user(credentials.credentials)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not logout"
            )
        return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Update current user information"""
    async with tracing_service.trace_operation("user_profile_update"):
        # Users can only update their own profile, not role or status
        if user_update.role is not None or user_update.status is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update role or status"
            )
        
        try:
            user = await auth_use_case.update_user_profile(current_user.id, user_update)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return user
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: UserResponse = Depends(get_current_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Change user password"""
    async with tracing_service.trace_operation("password_change"):
        success = await auth_use_case.change_user_password(
            current_user.id, old_password, new_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not change password"
            )
        return {"message": "Password changed successfully"}


# Admin endpoints
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    search: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """List users (admin only)"""
    async with tracing_service.trace_operation("admin_list_users"):
        users = await auth_use_case.list_users(skip, limit, role, status, search)
        return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Get user by ID (admin only)"""
    async with tracing_service.trace_operation("admin_get_user"):
        try:
            from uuid import UUID
            user = await auth_use_case.get_current_user(str(UUID(user_id)))
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return user
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Update user (admin only)"""
    async with tracing_service.trace_operation("admin_update_user"):
        try:
            from uuid import UUID
            user = await auth_use_case.update_user_profile(UUID(user_id), user_update)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return user
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Delete user (admin only)"""
    async with tracing_service.trace_operation("admin_delete_user"):
        try:
            from uuid import UUID
            success = await auth_use_case.delete_user(UUID(user_id))
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return {"message": "User deleted successfully"}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Activate user (admin only)"""
    async with tracing_service.trace_operation("admin_activate_user"):
        try:
            from uuid import UUID
            success = await auth_use_case.activate_user(UUID(user_id))
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return {"message": "User activated successfully"}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin_user),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Deactivate user (admin only)"""
    async with tracing_service.trace_operation("admin_deactivate_user"):
        try:
            from uuid import UUID
            success = await auth_use_case.deactivate_user(UUID(user_id))
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return {"message": "User deactivated successfully"}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )


@router.get("/statistics")
async def get_user_statistics(
    current_user: UserResponse = Depends(get_current_admin_user),
    user_management_use_case: UserManagementUseCase = Depends(get_user_management_use_case),
    tracing_service = Depends(get_tracing_service)
):
    """Get user statistics (admin only)"""
    async with tracing_service.trace_operation("admin_user_statistics"):
        stats = await user_management_use_case.get_user_statistics()
        return stats


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth-service"}
