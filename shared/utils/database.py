from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import redis
from clickhouse_driver import Client
from typing import Generator
import logging

from ..config.settings import settings

logger = logging.getLogger(__name__)

# PostgreSQL
engine = create_engine(
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}@"
    f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password,
    decode_responses=True
)

# ClickHouse
clickhouse_client = Client(
    host=settings.clickhouse_host,
    port=settings.clickhouse_port,
    database=settings.clickhouse_db,
    user=settings.clickhouse_user,
    password=settings.clickhouse_password
)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_redis() -> redis.Redis:
    """Get Redis client."""
    return redis_client


def get_clickhouse() -> Client:
    """Get ClickHouse client."""
    return clickhouse_client


class DatabaseManager:
    """Database connection manager with health checks."""
    
    @staticmethod
    async def check_postgres_health() -> bool:
        """Check PostgreSQL health."""
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False
    
    @staticmethod
    async def check_redis_health() -> bool:
        """Check Redis health."""
        try:
            redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    @staticmethod
    async def check_clickhouse_health() -> bool:
        """Check ClickHouse health."""
        try:
            clickhouse_client.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False
    
    @staticmethod
    async def initialize_databases():
        """Initialize database connections and create tables."""
        try:
            # Create PostgreSQL tables
            Base.metadata.create_all(bind=engine)
            logger.info("PostgreSQL tables created successfully")
            
            # Initialize ClickHouse tables
            await DatabaseManager._init_clickhouse_tables()
            logger.info("ClickHouse tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    @staticmethod
    async def _init_clickhouse_tables():
        """Initialize ClickHouse analytics tables."""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS query_metrics (
                timestamp DateTime,
                query_id String,
                query_text String,
                processing_time_ms UInt32,
                retrieval_count UInt32,
                generation_tokens UInt32,
                model_name String,
                service_name String
            ) ENGINE = MergeTree()
            ORDER BY timestamp
            """,
            """
            CREATE TABLE IF NOT EXISTS document_metrics (
                timestamp DateTime,
                document_id String,
                file_type String,
                size_bytes UInt64,
                processing_time_ms UInt32,
                chunk_count UInt32,
                status String
            ) ENGINE = MergeTree()
            ORDER BY timestamp
            """,
            """
            CREATE TABLE IF NOT EXISTS model_metrics (
                timestamp DateTime,
                model_name String,
                model_type String,
                memory_usage_mb UInt32,
                request_count UInt32,
                avg_processing_time_ms Float32
            ) ENGINE = MergeTree()
            ORDER BY timestamp
            """
        ]
        
        for table_sql in tables:
            try:
                clickhouse_client.execute(table_sql)
            except Exception as e:
                logger.error(f"Failed to create ClickHouse table: {e}")
                raise
