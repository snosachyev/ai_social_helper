"""Database connection management with dependency injection"""

from abc import ABC, abstractmethod
from typing import Generator, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
import logging
from contextlib import asynccontextmanager

from .models import Base
from ..config.settings import get_config


logger = logging.getLogger(__name__)


class DatabaseConnection(ABC):
    """Abstract database connection"""
    
    @abstractmethod
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
        pass
    
    @abstractmethod
    async def initialize(self):
        """Initialize database"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close database connection"""
        pass


class PostgresConnection(DatabaseConnection):
    """PostgreSQL connection implementation"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize PostgreSQL connection"""
        if self._initialized:
            return
        
        try:
            config = await get_config()
            db_config = config.database
            
            # Create async engine
            database_url = (
                f"postgresql+asyncpg://{db_config.username}:{db_config.password}@"
                f"{db_config.host}:{db_config.port}/{db_config.database}"
            )
            
            self.engine = create_async_engine(
                database_url,
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_timeout=db_config.pool_timeout,
                pool_recycle=db_config.pool_recycle,
                echo=config.service.debug
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self._initialized = True
            logger.info(f"PostgreSQL connection initialized: {db_config.host}:{db_config.port}/{db_config.database}")
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection: {e}")
            raise DatabaseConnectionError(f"Failed to initialize database: {str(e)}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
        if not self._initialized:
            await self.initialize()
        
        session = self.session_factory()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
    
    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL connection closed")


class SyncPostgresConnection(DatabaseConnection):
    """Synchronous PostgreSQL connection for legacy code"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize PostgreSQL connection"""
        if self._initialized:
            return
        
        try:
            config = await get_config()
            db_config = config.database
            
            # Create sync engine
            database_url = (
                f"postgresql+psycopg2://{db_config.username}:{db_config.password}@"
                f"{db_config.host}:{db_config.port}/{db_config.database}"
            )
            
            self.engine = create_engine(
                database_url,
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_timeout=db_config.pool_timeout,
                pool_recycle=db_config.pool_recycle,
                echo=config.service.debug
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.engine,
                autocommit=False,
                autoflush=False
            )
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            logger.info(f"Sync PostgreSQL connection initialized: {db_config.host}:{db_config.port}/{db_config.database}")
            
        except Exception as e:
            logger.error(f"Failed to initialize sync PostgreSQL connection: {e}")
            raise DatabaseConnectionError(f"Failed to initialize database: {str(e)}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[Session, None]:
        """Get database session"""
        if not self._initialized:
            await self.initialize()
        
        session = self.session_factory()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    async def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Sync PostgreSQL connection closed")


class DatabaseConnectionManager:
    """Database connection manager with health checks"""
    
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
        async for session in self.connection.get_session():
            yield session
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            async with self.connection.get_session() as session:
                # Simple health check query
                await session.execute("SELECT 1")
            
            return {
                "status": "healthy",
                "connection_type": type(self.connection).__name__
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_type": type(self.connection).__name__
            }
    
    async def initialize(self):
        """Initialize database connection"""
        await self.connection.initialize()
    
    async def close(self):
        """Close database connection"""
        await self.connection.close()


class DatabaseConnectionError(Exception):
    """Database connection errors"""
    pass


# Factory function
async def create_database_connection(use_async: bool = True) -> DatabaseConnectionManager:
    """Create database connection based on configuration"""
    if use_async:
        connection = PostgresConnection()
    else:
        connection = SyncPostgresConnection()
    
    return DatabaseConnectionManager(connection)
