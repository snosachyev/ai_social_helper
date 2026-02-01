from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
import logging

from shared.utils.database import engine, Base
from src.infrastructure.database.models import DocumentDB, ChunkDB
from src.presentation.api.document_routes import router
from shared.config.settings import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Document Service starting up...")
    
    # Create upload directory with proper permissions
    try:
        os.makedirs("./uploads", exist_ok=True, mode=0o777)
        logger.info("Upload directory created/verified")
    except Exception as e:
        logger.error(f"Failed to create upload directory: {e}")
    
    # Initialize database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database table creation failed: {e}")
    
    yield
    logger.info("Document Service shutting down...")


app = FastAPI(
    title="Document Ingestion Service",
    description="Document parsing and preprocessing service",
    version="1.0.0",
    lifespan=lifespan
)

# Include routes
app.include_router(router, prefix="/api/v1", tags=["documents"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug
    )
