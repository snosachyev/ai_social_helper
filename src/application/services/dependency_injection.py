"""Dependency injection container and configuration"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Type, TypeVar, Callable, Optional, Protocol, runtime_checkable, List
from dataclasses import dataclass, field
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


@runtime_checkable
class Factory(Protocol[T]):
    """Protocol for factory functions"""
    
    def __call__(self, **kwargs: Any) -> T:
        ...


@dataclass
class ServiceDescriptor:
    """Descriptor for a registered service"""
    service_type: Type
    implementation: Type = None
    factory: Callable = None
    instance: Any = None
    lifetime: str = "transient"  # singleton, scoped, transient
    dependencies: list = field(default_factory=list)


class DIContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped: Dict[str, Dict[Type, Any]] = {}
        self._current_scope: Optional[str] = None
    
    def register_singleton(
        self, 
        service_type: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[..., T] = None,
        instance: T = None
    ) -> "DIContainer":
        """Register a singleton service"""
        if sum(bool(x) for x in [implementation, factory, instance]) != 1:
            raise ValueError("Must provide exactly one of: implementation, factory, or instance")
        
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            instance=instance,
            lifetime="singleton"
        )
        return self
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation: Type[T] = None,
        factory: Callable[..., T] = None
    ) -> "DIContainer":
        """Register a scoped service"""
        if sum(bool(x) for x in [implementation, factory]) != 1:
            raise ValueError("Must provide exactly one of: implementation or factory")
        
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            lifetime="scoped"
        )
        return self
    
    def register_transient(
        self,
        service_type: Type[T],
        implementation: Type[T] = None,
        factory: Callable[..., T] = None
    ) -> "DIContainer":
        """Register a transient service"""
        if sum(bool(x) for x in [implementation, factory]) != 1:
            raise ValueError("Must provide exactly one of: implementation or factory")
        
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            lifetime="transient"
        )
        return self
    
    @asynccontextmanager
    async def create_scope(self):
        """Create a new scope for scoped services"""
        old_scope = self._current_scope
        scope_id = f"scope_{id(self)}"
        self._current_scope = scope_id
        self._scoped[scope_id] = {}
        
        try:
            yield self
        finally:
            # Cleanup scoped services
            if scope_id in self._scoped:
                scoped_services = self._scoped[scope_id]
                for service_instance in scoped_services.values():
                    if hasattr(service_instance, 'cleanup'):
                        try:
                            await service_instance.cleanup()
                        except Exception as e:
                            logger.warning(f"Error cleaning up scoped service: {e}")
                
                del self._scoped[scope_id]
            self._current_scope = old_scope
    
    async def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type} not registered")
        
        descriptor = self._services[service_type]
        
        # Check if instance is already created
        if descriptor.lifetime == "singleton":
            if service_type in self._singletons:
                return self._singletons[service_type]
        elif descriptor.lifetime == "scoped":
            if self._current_scope and service_type in self._scoped[self._current_scope]:
                return self._scoped[self._current_scope][service_type]
        
        # Create new instance
        instance = await self._create_instance(descriptor)
        
        # Store instance based on lifetime
        if descriptor.lifetime == "singleton":
            self._singletons[service_type] = instance
        elif descriptor.lifetime == "scoped":
            if self._current_scope:
                self._scoped[self._current_scope][service_type] = instance
        
        return instance
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance"""
        try:
            if descriptor.instance:
                return descriptor.instance
            elif descriptor.factory:
                # Resolve dependencies for factory
                dependencies = await self._resolve_dependencies(descriptor.dependencies)
                return descriptor.factory(**dependencies)
            elif descriptor.implementation:
                # Resolve dependencies for implementation
                dependencies = await self._resolve_dependencies(descriptor.dependencies)
                return descriptor.implementation(**dependencies)
            else:
                raise ValueError("No way to create instance")
        
        except Exception as e:
            logger.error(f"Failed to create instance of {descriptor.service_type}: {e}")
            raise
    
    async def _resolve_dependencies(self, dependency_types: List[Type]) -> Dict[str, Any]:
        """Resolve dependency instances"""
        dependencies = {}
        for dep_type in dependency_types:
            dependencies[dep_type.__name__.lower()] = await self.resolve(dep_type)
        return dependencies
    
    def auto_register(self, implementation: Type[T], lifetime: str = "transient") -> "DIContainer":
        """Auto-register a service by inspecting its type hints"""
        # This would inspect the class and auto-determine dependencies
        # For now, simple registration
        service_type = implementation
        if lifetime == "singleton":
            return self.register_singleton(service_type, implementation)
        elif lifetime == "scoped":
            return self.register_scoped(service_type, implementation)
        else:
            return self.register_transient(service_type, implementation)
    
    async def cleanup(self):
        """Cleanup all services"""
        # Cleanup singletons
        for service_instance in self._singletons.values():
            if hasattr(service_instance, 'cleanup'):
                try:
                    await service_instance.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up singleton service: {e}")
        
        self._singletons.clear()
        self._scoped.clear()


class ServiceConfiguration:
    """Configuration for service registration"""
    
    def __init__(self, container: DIContainer):
        self.container = container
    
    def configure_services(self) -> DIContainer:
        """Configure all services"""
        # This method will be overridden by specific configurations
        return self.container


class AppConfig:
    """Application configuration"""
    
    def __init__(self, **kwargs):
        self.settings = kwargs
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.settings[key] = value


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def configure_services(configurator: Callable[[DIContainer], DIContainer]) -> DIContainer:
    """Configure the global DI container"""
    container = get_container()
    return configurator(container)
