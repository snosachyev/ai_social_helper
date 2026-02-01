"""Authentication use cases"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from ..services.dependency_injection import DIContainer
from ...domain.entities.user import (
    User, UserCreate, UserUpdate, UserLogin, 
    Token, UserResponse, UserRole, UserStatus
)
from ...domain.services.auth_service import AuthService, TokenBlacklistService
from ...infrastructure.repositories.user_repository import UserRepository


class AuthUseCase:
    """Authentication use case"""
    
    def __init__(self, user_repository: UserRepository, auth_service: AuthService):
        self.user_repository = user_repository
        self.auth_service = auth_service
        self.token_blacklist = TokenBlacklistService()
    
    async def register_user(self, user_create: UserCreate) -> UserResponse:
        """Register new user"""
        # Check if user already exists
        if self.user_repository.check_email_exists(user_create.email):
            raise ValueError("Email already registered")
        
        if self.user_repository.check_username_exists(user_create.username):
            raise ValueError("Username already taken")
        
        # Hash password
        user_create = self.auth_service.hash_user_password(user_create)
        
        # Create user
        user = self.user_repository.create_user(user_create)
        
        return UserResponse.from_orm(user)
    
    async def login_user(self, user_login: UserLogin) -> Token:
        """Login user and return tokens"""
        # Get user by email
        user = self.user_repository.get_user_by_email(user_login.email)
        if not user:
            raise ValueError("Invalid credentials")
        
        # Check user status
        if not self.auth_service.is_active(user):
            raise ValueError("Account is not active")
        
        # Verify password (assuming user has password_hash attribute)
        # This would need to be implemented in the repository
        if not self.auth_service.authenticate_user(user, user_login.password):
            raise ValueError("Invalid credentials")
        
        # Update last login
        self.user_repository.update_last_login(user.id)
        
        # Create tokens
        tokens = self.auth_service.create_user_tokens(user)
        
        return Token(**tokens)
    
    async def refresh_token(self, refresh_token: str) -> Token:
        """Refresh access token"""
        # Verify refresh token
        token_data = self.auth_service.verify_token(refresh_token)
        if not token_data or not token_data.user_id:
            raise ValueError("Invalid refresh token")
        
        # Check if token is blacklisted
        if self.token_blacklist.is_token_blacklisted(refresh_token):
            raise ValueError("Token is blacklisted")
        
        # Get user
        user = self.user_repository.get_user_by_id(token_data.user_id)
        if not user or not self.auth_service.is_active(user):
            raise ValueError("User not found or inactive")
        
        # Create new tokens
        tokens = self.auth_service.create_user_tokens(user)
        
        # Blacklist old refresh token
        self.token_blacklist.blacklist_token(
            refresh_token, 
            datetime.utcnow() + timedelta(days=7)
        )
        
        return Token(**tokens)
    
    async def logout_user(self, token: str) -> bool:
        """Logout user and blacklist token"""
        token_data = self.auth_service.verify_token(token)
        if not token_data:
            return False
        
        # Blacklist token
        self.token_blacklist.blacklist_token(
            token,
            datetime.utcnow() + timedelta(minutes=self.auth_service.access_token_expire_minutes)
        )
        
        return True
    
    async def get_current_user(self, token: str) -> Optional[UserResponse]:
        """Get current user from token"""
        token_data = self.auth_service.verify_token(token)
        if not token_data or not token_data.user_id:
            return None
        
        # Check if token is blacklisted
        if self.token_blacklist.is_token_blacklisted(token):
            return None
        
        user = self.user_repository.get_user_by_id(token_data.user_id)
        if not user or not self.auth_service.is_active(user):
            return None
        
        return UserResponse.from_orm(user)
    
    async def update_user_profile(self, user_id: UUID, user_update: UserUpdate) -> Optional[UserResponse]:
        """Update user profile"""
        user = self.user_repository.update_user(user_id, user_update)
        if not user:
            return None
        
        return UserResponse.from_orm(user)
    
    async def change_user_password(self, user_id: UUID, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = self.user_repository.get_user_by_id(user_id)
        if not user:
            return False
        
        # Verify old password
        if not self.auth_service.authenticate_user(user, old_password):
            return False
        
        # Hash new password and update
        new_hashed_password = self.auth_service.get_password_hash(new_password)
        # This would need to be implemented in the repository
        # self.user_repository.update_password(user_id, new_hashed_password)
        
        return True
    
    async def deactivate_user(self, user_id: UUID) -> bool:
        """Deactivate user"""
        return self.user_repository.change_user_status(user_id, UserStatus.INACTIVE)
    
    async def activate_user(self, user_id: UUID) -> bool:
        """Activate user"""
        return self.user_repository.change_user_status(user_id, UserStatus.ACTIVE)
    
    async def suspend_user(self, user_id: UUID) -> bool:
        """Suspend user"""
        return self.user_repository.change_user_status(user_id, UserStatus.SUSPENDED)
    
    async def list_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None
    ) -> list[UserResponse]:
        """List users (admin only)"""
        users = self.user_repository.list_users(skip, limit, role, status, search)
        return [UserResponse.from_orm(user) for user in users]
    
    async def delete_user(self, user_id: UUID) -> bool:
        """Delete user (admin only)"""
        return self.user_repository.delete_user(user_id)
    
    def verify_user_permissions(self, user: User, required_role: UserRole = UserRole.USER) -> bool:
        """Verify user has required permissions"""
        return self.auth_service.validate_user_permissions(user, required_role)
    
    def is_admin(self, user: User) -> bool:
        """Check if user is admin"""
        return self.auth_service.is_admin(user)


class UserManagementUseCase:
    """User management use case for admin operations"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics"""
        total_users = self.user_repository.count_users()
        active_users = self.user_repository.get_active_users_count()
        
        # Get users by role
        admin_count = self.user_repository.count_users(role=UserRole.ADMIN)
        user_count = self.user_repository.count_users(role=UserRole.USER)
        viewer_count = self.user_repository.count_users(role=UserRole.VIEWER)
        
        # Get users by status
        active_count = self.user_repository.count_users(status=UserStatus.ACTIVE)
        inactive_count = self.user_repository.count_users(status=UserStatus.INACTIVE)
        suspended_count = self.user_repository.count_users(status=UserStatus.SUSPENDED)
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "by_role": {
                "admin": admin_count,
                "user": user_count,
                "viewer": viewer_count
            },
            "by_status": {
                "active": active_count,
                "inactive": inactive_count,
                "suspended": suspended_count
            }
        }
    
    async def get_recent_users(self, days: int = 7) -> list[UserResponse]:
        """Get users registered in the last N days"""
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        users = self.user_repository.get_users_created_in_period(start_date, end_date)
        return [UserResponse.from_orm(user) for user in users]
