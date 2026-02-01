"""Configuration management with dependency injection"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import os
import json
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "rag_db"
    username: str = "rag_user"
    password: str = "rag_password"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600


class RedisConfig(BaseModel):
    """Redis configuration"""
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class ClickHouseConfig(BaseModel):
    """ClickHouse configuration"""
    host: str = "localhost"
    port: int = 9000
    database: str = "rag_analytics"
    username: str = "default"
    password: Optional[str] = None
    compress: bool = True
    compress_block_size: int = 1048576


class VectorStoreConfig(BaseModel):
    """Vector store configuration"""
    store_type: str = "chroma"  # chroma, faiss
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_directory: str = "./chroma_db"
    faiss_index_path: str = "./faiss_index"
    dimension: int = 384
    metric: str = "cosine"


class ModelConfig(BaseModel):
    """Model configuration"""
    cache_dir: str = "./model_cache"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    generation_model: str = "microsoft/DialoGPT-medium"
    reranking_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    max_memory_gb: int = 16
    device: str = "auto"  # auto, cpu, cuda
    batch_size: int = 32


class ServiceConfig(BaseModel):
    """Service configuration"""
    name: str = "rag-service"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "INFO"


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""
    enable_prometheus: bool = True
    prometheus_port: int = 9090
    enable_tracing: bool = True
    tracing_backend: str = "jaeger"  # jaeger, phoenix
    tracing_endpoint: str = "http://localhost:14268/api/traces"
    enable_metrics: bool = True


class AuthConfig(BaseModel):
    """Authentication configuration"""
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    require_email_verification: bool = False
    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = 60
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15


class SecurityConfig(BaseModel):
    """Security configuration"""
    auth: AuthConfig = Field(default_factory=AuthConfig)
    enable_content_filter: bool = True
    enable_cors: bool = True
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]


class AppConfig(BaseModel):
    """Main application configuration"""
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    clickhouse: ClickHouseConfig = Field(default_factory=ClickHouseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


class ConfigurationProvider(ABC):
    """Abstract configuration provider"""
    
    @abstractmethod
    async def load_config(self) -> AppConfig:
        """Load configuration"""
        pass
    
    @abstractmethod
    async def save_config(self, config: AppConfig) -> bool:
        """Save configuration"""
        pass


class FileConfigurationProvider(ConfigurationProvider):
    """File-based configuration provider"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
    
    async def load_config(self) -> AppConfig:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    if self.config_path.suffix.lower() == '.json':
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)
                
                return AppConfig(**data)
            else:
                # Create default config
                config = AppConfig()
                await self.save_config(config)
                return config
                
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}")
    
    async def save_config(self, config: AppConfig) -> bool:
        """Save configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                if self.config_path.suffix.lower() == '.json':
                    json.dump(config.dict(), f, indent=2)
                else:
                    yaml.dump(config.dict(), f, default_flow_style=False)
            
            return True
            
        except Exception as e:
            raise ConfigurationError(f"Failed to save config: {e}")


class EnvironmentConfigurationProvider(ConfigurationProvider):
    """Environment variable configuration provider"""
    
    def __init__(self, prefix: str = "RAG_"):
        self.prefix = prefix
    
    async def load_config(self) -> AppConfig:
        """Load configuration from environment variables"""
        try:
            # Extract environment variables with prefix
            env_data = {}
            for key, value in os.environ.items():
                if key.startswith(self.prefix):
                    config_key = key[len(self.prefix):].lower()
                    env_data[config_key] = value
            
            # Convert nested keys (e.g., database_host -> database.host)
            config_dict = self._flatten_to_nested(env_data)
            
            return AppConfig(**config_dict)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load config from environment: {e}")
    
    async def save_config(self, config: AppConfig) -> bool:
        """Save configuration to environment variables (not implemented)"""
        # Environment variables are read-only
        return False
    
    def _flatten_to_nested(self, flat_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert flat dictionary to nested dictionary"""
        result = {}
        
        for key, value in flat_dict.items():
            parts = key.split('_')
            current = result
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return result


class CompositeConfigurationProvider(ConfigurationProvider):
    """Composite configuration provider that tries multiple sources"""
    
    def __init__(self, providers: List[ConfigurationProvider]):
        self.providers = providers
    
    async def load_config(self) -> AppConfig:
        """Load configuration from first successful provider"""
        for provider in self.providers:
            try:
                return await provider.load_config()
            except Exception as e:
                continue
        
        raise ConfigurationError("All configuration providers failed")
    
    async def save_config(self, config: AppConfig) -> bool:
        """Save configuration to all writable providers"""
        success = False
        for provider in self.providers:
            try:
                if await provider.save_config(config):
                    success = True
            except Exception:
                continue
        
        return success


class ConfigurationManager:
    """Configuration manager with caching and hot reload"""
    
    def __init__(self, provider: ConfigurationProvider):
        self.provider = provider
        self._config: Optional[AppConfig] = None
        self._config_hash: Optional[str] = None
    
    async def get_config(self) -> AppConfig:
        """Get current configuration"""
        if self._config is None:
            await self.reload_config()
        return self._config
    
    async def reload_config(self) -> AppConfig:
        """Reload configuration from provider"""
        self._config = await self.provider.load_config()
        self._config_hash = self._calculate_hash(self._config)
        return self._config
    
    async def update_config(self, config: AppConfig) -> bool:
        """Update configuration"""
        success = await self.provider.save_config(config)
        if success:
            await self.reload_config()
        return success
    
    def _calculate_hash(self, config: AppConfig) -> str:
        """Calculate configuration hash for change detection"""
        import hashlib
        config_str = json.dumps(config.dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()


class ConfigurationError(Exception):
    """Configuration related errors"""
    pass


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get global configuration manager"""
    global _config_manager
    if _config_manager is None:
        # Create default composite provider
        provider = CompositeConfigurationProvider([
            FileConfigurationProvider(),
            EnvironmentConfigurationProvider()
        ])
        _config_manager = ConfigurationManager(provider)
    return _config_manager


async def get_config() -> AppConfig:
    """Get current application configuration"""
    manager = get_config_manager()
    return await manager.get_config()
