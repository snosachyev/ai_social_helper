"""Authentication domain service"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import bcrypt
from passlib.context import CryptContext
from jose import jwt

from ..entities.user import User, UserCredentials, UserCreate, TokenData, UserRole
from ...infrastructure.config.settings import get_config


class AuthService:
    """Authentication service for user management and token handling"""
    
    def __init__(self):
        self.config = get_config()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = self.config.auth.secret_key
        self.algorithm = self.config.auth.algorithm
        self.access_token_expire_minutes = self.config.auth.access_token_expire_minutes
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)  # Refresh tokens last longer
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify JWT token and extract data"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role")
            exp: int = payload.get("exp")
            
            if user_id is None:
                return None
                
            return TokenData(
                user_id=UUID(user_id) if user_id else None,
                email=email,
                role=UserRole(role) if role else None,
                exp=exp
            )
        except jwt.PyJWTError:
            return None
    
    def authenticate_user(self, user: User, password: str) -> bool:
        """Authenticate user with password"""
        if not user or not hasattr(user, 'password_hash'):
            return False
        return self.verify_password(password, user.password_hash)
    
    def create_user_tokens(self, user: User) -> Dict[str, Any]:
        """Create access and refresh tokens for user"""
        access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
        access_token = self.create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            },
            expires_delta=access_token_expires
        )
        
        refresh_token = self.create_refresh_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            }
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60
        }
    
    def hash_user_password(self, user_create: UserCreate) -> UserCreate:
        """Hash password in user creation data"""
        user_data = user_create.dict()
        user_data["password"] = self.get_password_hash(user_data["password"])
        return UserCreate(**user_data)
    
    def validate_user_permissions(self, user: User, required_role: UserRole = UserRole.USER) -> bool:
        """Validate if user has required permissions"""
        if user.status.value != "active":
            return False
            
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.USER: 2,
            UserRole.ADMIN: 3
        }
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    def is_admin(self, user: User) -> bool:
        """Check if user is admin"""
        return user.role == UserRole.ADMIN
    
    def is_active(self, user: User) -> bool:
        """Check if user is active"""
        return user.status.value == "active"


class TokenBlacklistService:
    """Service for managing token blacklist"""
    
    def __init__(self):
        self.blacklisted_tokens: Dict[str, datetime] = {}
    
    def blacklist_token(self, token: str, expires_at: datetime):
        """Add token to blacklist"""
        self.blacklisted_tokens[token] = expires_at
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        if token not in self.blacklisted_tokens:
            return False
        
        # Remove expired tokens from blacklist
        if datetime.utcnow() > self.blacklisted_tokens[token]:
            del self.blacklisted_tokens[token]
            return False
            
        return True
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens from blacklist"""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, expires_at in self.blacklisted_tokens.items()
            if now > expires_at
        ]
        
        for token in expired_tokens:
            del self.blacklisted_tokens[token]
