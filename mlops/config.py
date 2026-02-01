"""
MLOps Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class MLOpsConfig(BaseSettings):
    # MLflow Configuration
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "rag_retraining"
    mlflow_registry_uri: str = "http://localhost:5000"
    
    # ClickHouse Configuration
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_database: str = "rag_features"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    
    # MinIO Configuration
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "rag-artifacts"
    minio_secure: bool = False
    
    # Model Registry Configuration
    model_registry_stage: str = "Production"
    model_canary_threshold: float = 0.05
    model_rollback_enabled: bool = True
    
    # Retraining Configuration
    retraining_schedule: str = "@daily"
    retraining_data_path: str = "/data/retraining"
    retraining_min_samples: int = 100
    
    # Deployment Configuration
    deployment_strategy: str = "canary"
    canary_traffic_percentage: int = 10
    rollback_timeout_minutes: int = 30
    
    class Config:
        env_prefix = "MLOPS_"
        env_file = ".env"


config = MLOpsConfig()
