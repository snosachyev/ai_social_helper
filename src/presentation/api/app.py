"""FastAPI application with clean architecture and dependency injection"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from .query_controller import router as query_router
from .document_controller import router as document_router
from .auth_controller import router as auth_router
from ...application.services.dependency_injection import get_container, configure_services
from ...infrastructure.config.settings import get_config
from ...infrastructure.tracing.phoenix_tracer import create_tracer, TracingService



logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with proper cleanup"""
    logger.info("RAG System starting up...")
    
    try:
        # Initialize configuration
        config = await get_config()
        logger.info(f"Configuration loaded: {config.service.name} v{config.service.version}")
        
        # Initialize dependency injection container
        container = get_container()
        await configure_services(container)
        logger.info("Dependency injection container configured")
        
        # Initialize tracing
        tracer = await create_tracer(config.monitoring.dict())
        container.register_singleton(type(tracer), instance=tracer)
        
        tracing_service = TracingService(tracer)
        container.register_singleton(TracingService, instance=tracing_service)
        logger.info("Tracing service initialized")
        
        # Store container in app state for access
        app.state.container = container
        app.state.config = config
        
        logger.info("RAG System startup complete")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    finally:
        logger.info("RAG System shutting down...")
        
        # Cleanup resources
        try:
            if hasattr(app.state, 'container'):
                container = app.state.container
                await container.cleanup()
                logger.info("Dependency injection container cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="RAG System API",
        description="Production-ready RAG system with clean architecture",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add middleware
    setup_middleware(app)
    
    # Add routers
    app.include_router(auth_router)
    app.include_router(query_router)
    app.include_router(document_router)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI):
    """Setup application middleware"""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # GZip middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


def setup_exception_handlers(app: FastAPI):
    """Setup custom exception handlers"""
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error in {request.url}: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid request",
                "message": str(exc),
                "type": "value_error"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception in {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "type": "internal_error"
            }
        )


# Create application instance
app = create_application()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RAG System API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check configuration
        config = await get_config()
        
        # Check DI container
        container = get_container()
        
        return {
            "status": "healthy",
            "service": config.service.name,
            "version": config.service.version,
            "components": {
                "configuration": "ok",
                "dependency_injection": "ok",
                "tracing": "ok" if config.monitoring.enable_tracing else "disabled"
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/info")
async def app_info():
    """Application information endpoint"""
    try:
        config = await get_config()
        
        return {
            "service": {
                "name": config.service.name,
                "version": config.service.version,
                "debug": config.service.debug
            },
            "features": {
                "tracing": config.monitoring.enable_tracing,
                "prometheus": config.monitoring.enable_prometheus,
                "rate_limiting": config.security.enable_rate_limiting,
                "content_filter": config.security.enable_content_filter
            },
            "models": {
                "embedding": config.model.embedding_model,
                "generation": config.model.generation_model,
                "reranking": config.model.reranking_model
            },
            "vector_store": {
                "type": config.vector_store.store_type,
                "dimension": config.vector_store.dimension
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get app info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get application information")


if __name__ == "__main__":
    import uvicorn
    
    async def run_server():
        """Run the server with configuration"""
        config = await get_config()
        
        uvicorn.run(
            "app:app",
            host=config.service.host,
            port=config.service.port,
            reload=config.service.debug,
            workers=config.service.workers if not config.service.debug else 1,
            log_level=config.service.log_level.lower()
        )
    
    import asyncio
    asyncio.run(run_server())
