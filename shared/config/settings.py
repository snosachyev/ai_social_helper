from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "rag-service"
    service_version: str = "1.0.0"
    debug: bool = False
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    
    # Database Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "rag_db"
    postgres_user: str = "rag_user"
    postgres_password: str = "rag_password"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_documents: str = "documents"
    kafka_topic_queries: str = "queries"
    kafka_topic_models: str = "models"
    
    # ClickHouse Configuration
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_db: str = "rag_analytics"
    clickhouse_user: str = "default"
    clickhouse_password: Optional[str] = None
    
    # Model Configuration
    hf_cache_dir: str = os.getenv("HF_CACHE_DIR", os.getenv("HF_HOME", "./model_cache"))
    embedding_model: str = "/app/hf_cache/sentence-transformers-paraphrase-multilingual-MiniLM-L12-v2"  # Симлинк на модель
    generation_model: str = "microsoft/DialoGPT-medium"
    max_memory_gb: int = 16
    hf_download_timeout: int = 60  # Тайм-аут для загрузки моделей в секундах
    
    # Vector Store Configuration
    vector_store_type: str = "chroma"  # chroma, faiss
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_directory: str = "./chroma_db"
    
    # MLflow Configuration
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "rag-system"
    
    # Security Configuration
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Monitoring Configuration
    prometheus_port: int = 9090
    log_level: str = "INFO"
    
    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 30
    circuit_breaker_expected_exception: str = "Exception"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
