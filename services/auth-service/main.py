"""Authentication service main entry point"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.auth_controller import router as auth_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting authentication service...")
    yield
    logger.info("Shutting down authentication service...")


def create_auth_app() -> FastAPI:
    """Create authentication service application"""
    app = FastAPI(
        title="RAG Authentication Service",
        description="Authentication and authorization service for RAG system",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include auth router
    app.include_router(auth_router, tags=["authentication"])
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {"message": "RAG Authentication Service", "status": "running"}
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "auth-service"}
    
    return app


# Create the application instance
app = create_auth_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8007,
        log_level="info"
    )
