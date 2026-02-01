"""User domain entities"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User roles"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    """User status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(BaseModel):
    """User entity"""
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


class UserCredentials(BaseModel):
    """User credentials for authentication"""
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    """User creation request"""
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    password: str
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    """User update request"""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response (without sensitive data)"""
    id: UUID
    email: EmailStr
    username: str
    full_name: Optional[str]
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    user_metadata: Dict[str, Any]
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Authentication token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """Token data"""
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    exp: Optional[int] = None
