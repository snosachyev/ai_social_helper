"""Base database models"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Create base class for all models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()

# Database engine (will be configured properly in connection.py)
engine = None
SessionLocal = None


def create_database_engine(database_url: str):
    """Create database engine"""
    global engine, SessionLocal
    
    if "sqlite" in database_url:
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(database_url)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return engine


def get_db_session():
    """Get database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call create_database_engine first.")
    
    return SessionLocal()
