"""
Canary Deployment and Rollback Mechanisms
"""
import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import numpy as np
import logging
from .model_registry import RAGModelRegistry
from .config import config


class DeploymentStatus(Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    CANARY = "canary"
    PRODUCTION = "production"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentConfig:
    model_name: str
    model_version: str
    deployment_type: str  # "canary" or "production"
    traffic_percentage: int = 10
    health_check_interval: int = 60  # seconds
    max_failure_threshold: int = 5
    rollback_timeout: int = 1800  # 30 minutes
    canary_duration: int = 3600  # 1 hour


@dataclass
class HealthMetrics:
    latency_ms: float
    error_rate: float
    throughput_qps: float
    accuracy: float
    timestamp: datetime


class CanaryDeployment:
    """Canary deployment manager for RAG models"""
    
    def __init__(self):
        self.registry = RAGModelRegistry()
        self.deployments: Dict[str, DeploymentConfig] = {}
        self.health_metrics: Dict[str, List[HealthMetrics]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Service endpoints
        self.service_endpoints = {
            "api_gateway": "http://localhost:8000",
            "embedding_service": "http://localhost:8002",
            "retrieval_service": "http://localhost:8004",
            "generation_service": "http://localhost:8005"
        }
    
    async def deploy_canary(self, deployment_config: DeploymentConfig) -> Dict[str, Any]:
        """Deploy model as canary"""
        deployment_id = f"{deployment_config.model_name}_{deployment_config.model_version}_{int(time.time())}"
        
        try:
            # Update deployment status
            self.deployments[deployment_id] = deployment_config
            self.health_metrics[deployment_id] = []
            
            # Step 1: Deploy to canary environment
            await self._deploy_to_service(deployment_config, "canary")
            
            # Step 2: Configure traffic routing
            await self._configure_traffic_routing(deployment_config)
            
            # Step 3: Start health monitoring
            monitoring_task = asyncio.create_task(
                self._monitor_canary_health(deployment_id)
            )
            
            return {
                "deployment_id": deployment_id,
                "status": DeploymentStatus.CANARY.value,
                "message": "Canary deployment initiated successfully",
                "config": deployment_config.__dict__
            }
            
        except Exception as e:
            self.logger.error(f"Canary deployment failed: {e}")
            return {
                "deployment_id": deployment_id,
                "status": DeploymentStatus.FAILED.value,
                "message": str(e)
            }
    
    async def _deploy_to_service(self, config: DeploymentConfig, environment: str):
        """Deploy model to specific service"""
        # Get model artifact from MinIO
        model_info = self.registry.artifact_store.get_model_metadata(
            config.model_name, config.model_version
        )
        
        if not model_info:
            raise ValueError(f"Model {config.model_name}:{config.model_version} not found")
        
        # Deploy to appropriate service based on model type
        if "embedding" in config.model_name:
            service_url = self.service_endpoints["embedding_service"]
        elif "retrieval" in config.model_name:
            service_url = self.service_endpoints["retrieval_service"]
        elif "generation" in config.model_name:
            service_url = self.service_endpoints["generation_service"]
        else:
            service_url = self.service_endpoints["api_gateway"]
        
        # Call deployment API
        async with aiohttp.ClientSession() as session:
            payload = {
                "model_name": config.model_name,
                "model_version": config.model_version,
                "environment": environment,
                "model_uri": model_info.get("model_uri", ""),
                "metadata": model_info
            }
            
            async with session.post(f"{service_url}/deploy", json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Deployment failed: {await response.text()}")
                
                return await response.json()
    
    async def _configure_traffic_routing(self, config: DeploymentConfig):
        """Configure traffic routing for canary deployment"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model_name": config.model_name,
                "canary_version": config.model_version,
                "traffic_percentage": config.traffic_percentage,
                "routing_strategy": "weighted"
            }
            
            async with session.post(
                f"{self.service_endpoints['api_gateway']}/traffic-routing",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Traffic routing failed: {await response.text()}")
                
                return await response.json()
    
    async def _monitor_canary_health(self, deployment_id: str):
        """Monitor canary deployment health"""
        config = self.deployments[deployment_id]
        start_time = datetime.now()
        
        while True:
            try:
                # Check if canary duration exceeded
                if (datetime.now() - start_time).seconds > config.canary_duration:
                    await self._promote_to_production(deployment_id)
                    break
                
                # Collect health metrics
                metrics = await self._collect_health_metrics(config)
                self.health_metrics[deployment_id].append(metrics)
                
                # Evaluate health
                health_status = self._evaluate_health(deployment_id)
                
                if health_status["is_healthy"]:
                    self.logger.info(f"Canary {deployment_id} is healthy")
                else:
                    self.logger.warning(f"Canary {deployment_id} health issues: {health_status['issues']}")
                    
                    # Check if rollback needed
                    if health_status["should_rollback"]:
                        await self._rollback_deployment(deployment_id, health_status["reason"])
                        break
                
                # Wait for next check
                await asyncio.sleep(config.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(config.health_check_interval)
    
    async def _collect_health_metrics(self, config: DeploymentConfig) -> HealthMetrics:
        """Collect health metrics for the deployed model"""
        # Query metrics from monitoring endpoints
        async with aiohttp.ClientSession() as session:
            # Get latency metrics
            async with session.get(
                f"{self.service_endpoints['api_gateway']}/metrics/latency",
                params={"model_name": config.model_name, "model_version": config.model_version}
            ) as response:
                latency_data = await response.json()
                latency_ms = latency_data.get("avg_latency_ms", 0)
            
            # Get error rate
            async with session.get(
                f"{self.service_endpoints['api_gateway']}/metrics/errors",
                params={"model_name": config.model_name, "model_version": config.model_version}
            ) as response:
                error_data = await response.json()
                error_rate = error_data.get("error_rate", 0)
            
            # Get throughput
            async with session.get(
                f"{self.service_endpoints['api_gateway']}/metrics/throughput",
                params={"model_name": config.model_name, "model_version": config.model_version}
            ) as response:
                throughput_data = await response.json()
                throughput_qps = throughput_data.get("throughput_qps", 0)
            
            # Get accuracy (from feature store)
            accuracy = await self._get_model_accuracy(config)
            
            return HealthMetrics(
                latency_ms=latency_ms,
                error_rate=error_rate,
                throughput_qps=throughput_qps,
                accuracy=accuracy,
                timestamp=datetime.now()
            )
    
    async def _get_model_accuracy(self, config: DeploymentConfig) -> float:
        """Get model accuracy from feature store"""
        from .feature_store import ClickHouseFeatureStore
        
        feature_store = ClickHouseFeatureStore()
        
        # Get recent performance metrics
        metrics = feature_store.client.execute("""
            SELECT avg(relevance_score)
            FROM query_features
            WHERE model_name = %(model_name)s
            AND model_version = %(model_version)s
            AND timestamp > now() - INTERVAL 1 HOUR
        """, {
            'model_name': config.model_name,
            'model_version': config.model_version
        })
        
        return metrics[0][0] if metrics else 0.0
    
    def _evaluate_health(self, deployment_id: str) -> Dict[str, Any]:
        """Evaluate deployment health based on collected metrics"""
        metrics = self.health_metrics[deployment_id]
        
        if len(metrics) < 5:  # Need sufficient data points
            return {
                "is_healthy": True,
                "issues": ["Insufficient data points"],
                "should_rollback": False
            }
        
        # Calculate recent averages
        recent_metrics = metrics[-5:]  # Last 5 data points
        
        avg_latency = np.mean([m.latency_ms for m in recent_metrics])
        avg_error_rate = np.mean([m.error_rate for m in recent_metrics])
        avg_throughput = np.mean([m.throughput_qps for m in recent_metrics])
        avg_accuracy = np.mean([m.accuracy for m in recent_metrics])
        
        issues = []
        should_rollback = False
        
        # Check latency threshold
        if avg_latency > 1000:  # 1 second
            issues.append(f"High latency: {avg_latency:.2f}ms")
            if avg_latency > 2000:
                should_rollback = True
        
        # Check error rate
        if avg_error_rate > 0.05:  # 5%
            issues.append(f"High error rate: {avg_error_rate:.2%}")
            if avg_error_rate > 0.1:
                should_rollback = True
        
        # Check accuracy
        if avg_accuracy < 0.7:  # 70%
            issues.append(f"Low accuracy: {avg_accuracy:.2f}")
            if avg_accuracy < 0.5:
                should_rollback = True
        
        # Check throughput
        if avg_throughput < 1.0:  # 1 query per second
            issues.append(f"Low throughput: {avg_throughput:.2f} qps")
        
        return {
            "is_healthy": len(issues) == 0,
            "issues": issues,
            "should_rollback": should_rollback,
            "metrics": {
                "avg_latency_ms": avg_latency,
                "avg_error_rate": avg_error_rate,
                "avg_throughput_qps": avg_throughput,
                "avg_accuracy": avg_accuracy
            }
        }
    
    async def _promote_to_production(self, deployment_id: str):
        """Promote canary to production"""
        config = self.deployments[deployment_id]
        
        try:
            # Promote in model registry
            success = self.registry.promote_to_production(
                model_name=config.model_name,
                model_version=config.model_version
            )
            
            if success:
                # Update traffic routing to 100%
                await self._update_traffic_routing(config, 100)
                
                self.logger.info(f"Canary {deployment_id} promoted to production")
                
                # Update deployment status
                config.deployment_type = "production"
                config.traffic_percentage = 100
                
            else:
                self.logger.error(f"Failed to promote {deployment_id} to production")
                
        except Exception as e:
            self.logger.error(f"Error promoting to production: {e}")
    
    async def _rollback_deployment(self, deployment_id: str, reason: str):
        """Rollback deployment due to health issues"""
        config = self.deployments[deployment_id]
        
        try:
            # Rollback in model registry
            success = self.registry.rollback_model(
                model_name=config.model_name
            )
            
            if success:
                # Reset traffic routing
                await self._reset_traffic_routing(config)
                
                self.logger.info(f"Deployment {deployment_id} rolled back: {reason}")
                
                # Update deployment status
                config.deployment_type = "rolled_back"
                
            else:
                self.logger.error(f"Failed to rollback {deployment_id}")
                
        except Exception as e:
            self.logger.error(f"Error during rollback: {e}")
    
    async def _update_traffic_routing(self, config: DeploymentConfig, traffic_percentage: int):
        """Update traffic routing percentage"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model_name": config.model_name,
                "canary_version": config.model_version,
                "traffic_percentage": traffic_percentage,
                "routing_strategy": "weighted"
            }
            
            async with session.post(
                f"{self.service_endpoints['api_gateway']}/traffic-routing",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Traffic routing update failed: {await response.text()}")
    
    async def _reset_traffic_routing(self, config: DeploymentConfig):
        """Reset traffic routing to previous stable version"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model_name": config.model_name,
                "reset_to_stable": True
            }
            
            async with session.post(
                f"{self.service_endpoints['api_gateway']}/traffic-routing",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Traffic routing reset failed: {await response.text()}")
    
    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get deployment status and metrics"""
        if deployment_id not in self.deployments:
            return {"error": "Deployment not found"}
        
        config = self.deployments[deployment_id]
        metrics = self.health_metrics.get(deployment_id, [])
        
        return {
            "deployment_id": deployment_id,
            "config": config.__dict__,
            "status": config.deployment_type,
            "metrics_count": len(metrics),
            "latest_metrics": metrics[-1].__dict__ if metrics else None,
            "health_evaluation": self._evaluate_health(deployment_id) if metrics else None
        }
    
    def list_deployments(self) -> List[Dict[str, Any]]:
        """List all active deployments"""
        deployments = []
        
        for deployment_id, config in self.deployments.items():
            status = self.get_deployment_status(deployment_id)
            deployments.append(status)
        
        return deployments


class RollbackManager:
    """Rollback manager for quick model version rollback"""
    
    def __init__(self):
        self.registry = RAGModelRegistry()
        self.canary_deployment = CanaryDeployment()
        self.logger = logging.getLogger(__name__)
    
    async def emergency_rollback(self, model_name: str, reason: str = "Emergency rollback") -> Dict[str, Any]:
        """Perform emergency rollback to previous stable version"""
        try:
            # Get current production version
            current_prod = self.registry.tracker.get_production_model(model_name)
            
            if not current_prod:
                return {
                    "success": False,
                    "message": "No production model found"
                }
            
            # Find previous stable version
            versions = self.registry.tracker.get_model_versions(model_name)
            previous_version = None
            
            for version in versions:
                if (version['version'] != current_prod['version'] and 
                    version['stage'] in ["Archived", "Staging"]):
                    previous_version = version['version']
                    break
            
            if not previous_version:
                return {
                    "success": False,
                    "message": "No previous version found for rollback"
                }
            
            # Perform rollback
            success = self.registry.rollback_model(model_name, previous_version)
            
            if success:
                # Cancel any ongoing canary deployments
                await self._cancel_canary_deployments(model_name)
                
                # Reset traffic routing
                await self._reset_all_traffic_routing(model_name)
                
                self.logger.info(f"Emergency rollback completed for {model_name}: {reason}")
                
                return {
                    "success": True,
                    "from_version": current_prod['version'],
                    "to_version": previous_version,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "message": "Rollback failed in model registry"
                }
                
        except Exception as e:
            self.logger.error(f"Emergency rollback failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def _cancel_canary_deployments(self, model_name: str):
        """Cancel any ongoing canary deployments for the model"""
        deployments = self.canary_deployment.list_deployments()
        
        for deployment in deployments:
            config = deployment.get("config", {})
            if config.get("model_name") == model_name and config.get("deployment_type") == "canary":
                # Cancel the deployment
                deployment_id = deployment.get("deployment_id")
                if deployment_id in self.canary_deployment.deployments:
                    del self.canary_deployment.deployments[deployment_id]
                if deployment_id in self.canary_deployment.health_metrics:
                    del self.canary_deployment.health_metrics[deployment_id]
    
    async def _reset_all_traffic_routing(self, model_name: str):
        """Reset all traffic routing for the model"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model_name": model_name,
                "reset_to_stable": True
            }
            
            async with session.post(
                f"{self.canary_deployment.service_endpoints['api_gateway']}/traffic-routing",
                json=payload
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to reset traffic routing: {await response.text()}")
    
    def get_rollback_history(self, model_name: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get rollback history for a model"""
        # This would typically query a rollback events table
        # For now, return placeholder data
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "model_name": model_name,
                "from_version": "1.2.3",
                "to_version": "1.2.2",
                "reason": "High error rate detected",
                "success": True
            }
        ]
