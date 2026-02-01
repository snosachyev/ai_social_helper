"""User repository implementation"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database.user_models import User as UserModel, UserStatus, UserRole
from ...domain.entities.user import User, UserCreate, UserUpdate


class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_create: UserCreate) -> User:
        """Create new user"""
        db_user = UserModel(
            email=user_create.email,
            username=user_create.username,
            full_name=user_create.full_name,
            password_hash=user_create.password,  # Should be already hashed
            role=user_create.role,
            status=UserStatus.ACTIVE,
            user_metadata={}
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        return self._to_domain_user(db_user)
    
    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_domain_user(db_user) if db_user else None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        db_user = self.db.query(UserModel).filter(UserModel.email == email).first()
        return self._to_domain_user(db_user) if db_user else None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        db_user = self.db.query(UserModel).filter(UserModel.username == username).first()
        return self._to_domain_user(db_user) if db_user else None
    
    def get_user_by_email_or_username(self, identifier: str) -> Optional[User]:
        """Get user by email or username"""
        db_user = self.db.query(UserModel).filter(
            or_(UserModel.email == identifier, UserModel.username == identifier)
        ).first()
        return self._to_domain_user(db_user) if db_user else None
    
    def update_user(self, user_id: UUID, user_update: UserUpdate) -> Optional[User]:
        """Update user"""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return None
        
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_user)
        
        return self._to_domain_user(db_user)
    
    def delete_user(self, user_id: UUID) -> bool:
        """Delete user"""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return False
        
        self.db.delete(db_user)
        self.db.commit()
        return True
    
    def list_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None
    ) -> List[User]:
        """List users with filters"""
        query = self.db.query(UserModel)
        
        if role:
            query = query.filter(UserModel.role == role)
        
        if status:
            query = query.filter(UserModel.status == status)
        
        if search:
            query = query.filter(
                or_(
                    UserModel.email.ilike(f"%{search}%"),
                    UserModel.username.ilike(f"%{search}%"),
                    UserModel.full_name.ilike(f"%{search}%")
                )
            )
        
        db_users = query.offset(skip).limit(limit).all()
        return [self._to_domain_user(user) for user in db_users]
    
    def count_users(
        self,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None
    ) -> int:
        """Count users with filters"""
        query = self.db.query(UserModel)
        
        if role:
            query = query.filter(UserModel.role == role)
        
        if status:
            query = query.filter(UserModel.status == status)
        
        if search:
            query = query.filter(
                or_(
                    UserModel.email.ilike(f"%{search}%"),
                    UserModel.username.ilike(f"%{search}%"),
                    UserModel.full_name.ilike(f"%{search}%")
                )
            )
        
        return query.count()
    
    def update_last_login(self, user_id: UUID) -> bool:
        """Update user last login time"""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return False
        
        db_user.last_login = datetime.utcnow()
        self.db.commit()
        return True
    
    def change_user_status(self, user_id: UUID, status: UserStatus) -> bool:
        """Change user status"""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return False
        
        db_user.status = status
        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def check_email_exists(self, email: str) -> bool:
        """Check if email exists"""
        return self.db.query(UserModel).filter(UserModel.email == email).first() is not None
    
    def check_username_exists(self, username: str) -> bool:
        """Check if username exists"""
        return self.db.query(UserModel).filter(UserModel.username == username).first() is not None
    
    def get_active_users_count(self) -> int:
        """Get count of active users"""
        return self.db.query(UserModel).filter(UserModel.status == UserStatus.ACTIVE).count()
    
    def get_users_created_in_period(self, start_date: datetime, end_date: datetime) -> List[User]:
        """Get users created in specific period"""
        db_users = self.db.query(UserModel).filter(
            and_(
                UserModel.created_at >= start_date,
                UserModel.created_at <= end_date
            )
        ).all()
        return [self._to_domain_user(user) for user in db_users]
    
    def _to_domain_user(self, db_user: UserModel) -> User:
        """Convert database user to domain user"""
        return User(
            id=db_user.id,
            email=db_user.email,
            username=db_user.username,
            full_name=db_user.full_name,
            role=db_user.role,
            status=db_user.status,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
            last_login=db_user.last_login,
            user_metadata=db_user.user_metadata or {}
        )
