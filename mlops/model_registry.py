"""
Model Registry Strategy and Versioning Management
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import numpy as np
from .mlflow_tracker import MLflowTracker, RAGModelTracker
from .config import config
from .artifact_store import MinIOArtifactStore


class ModelRegistryStrategy:
    """Model registry strategy with versioning and lifecycle management"""
    
    def __init__(self):
        self.tracker = MLflowTracker()
        self.artifact_store = MinIOArtifactStore()
        
        # Model lifecycle stages
        self.stages = ["Development", "Staging", "Canary", "Production", "Archived"]
        
        # Versioning strategy
        self.version_strategy = {
            "major_threshold": 0.15,  # 15% improvement for major version
            "minor_threshold": 0.05,  # 5% improvement for minor version
            "patch_threshold": 0.01   # 1% improvement for patch version
        }
    
    def calculate_version_bump(self, current_metrics: Dict[str, float], 
                              new_metrics: Dict[str, float]) -> str:
        """Calculate version bump type based on performance improvement"""
        # Use F1 score as primary metric for version bump decision
        primary_metric = "f1_score"
        
        if primary_metric not in current_metrics or primary_metric not in new_metrics:
            return "patch"  # Default to patch if metrics unavailable
        
        current_score = current_metrics[primary_metric]
        new_score = new_metrics[primary_metric]
        
        if current_score == 0:
            return "major"  # First model version
        
        improvement = (new_score - current_score) / current_score
        
        if improvement >= self.version_strategy["major_threshold"]:
            return "major"
        elif improvement >= self.version_strategy["minor_threshold"]:
            return "minor"
        elif improvement >= self.version_strategy["patch_threshold"]:
            return "patch"
        else:
            return "no-bump"  # No version bump if improvement is too small
    
    def get_next_version(self, model_name: str, bump_type: str) -> str:
        """Get next version number based on bump type"""
        versions = self.tracker.get_model_versions(model_name)
        
        if not versions:
            return "1.0.0"  # First version
        
        # Get latest production or staging version
        latest_version = None
        for version in versions:
            if version['stage'] in ["Production", "Staging"]:
                latest_version = version['version']
                break
        
        if not latest_version:
            latest_version = versions[0]['version']
        
        # Parse version string
        try:
            major, minor, patch = map(int, latest_version.split('.'))
        except:
            major, minor, patch = 1, 0, 0
        
        # Increment based on bump type
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1
        else:
            return latest_version  # No bump
        
        return f"{major}.{minor}.{patch}"
    
    def register_new_model(self, model_name: str, run_id: str, 
                          metrics: Dict[str, float], metadata: Dict[str, Any]) -> str:
        """Register new model with appropriate version"""
        # Get current production model metrics
        current_prod = self.tracker.get_production_model(model_name)
        current_metrics = {}
        
        if current_prod:
            run = self.tracker.client.get_run(current_prod['run_id'])
            current_metrics = run.data.metrics
        
        # Calculate version bump
        bump_type = self.calculate_version_bump(current_metrics, metrics)
        
        if bump_type == "no-bump":
            # Still register but with same version + suffix
            next_version = self.get_next_version(model_name, "patch") + "-experimental"
        else:
            next_version = self.get_next_version(model_name, bump_type)
        
        # Register model
        version = self.tracker.register_model(
            run_id=run_id,
            model_name=model_name,
            stage="Staging",
            description=f"Registered on {datetime.now().isoformat()} - Version bump: {bump_type}"
        )
        
        # Add version metadata
        version_metadata = {
            'version_type': bump_type,
            'registration_date': datetime.now().isoformat(),
            'metrics': metrics,
            'previous_version': current_prod['version'] if current_prod else None,
            'improvement': {
                metric: (metrics.get(metric, 0) - current_metrics.get(metric, 0)) / current_metrics.get(metric, 1)
                for metric in metrics.keys() if metric in current_metrics and current_metrics.get(metric, 0) > 0
            }
        }
        
        # Store additional metadata in MinIO
        self.artifact_store.upload_model(
            model_path="",  # Model already uploaded during training
            model_name=model_name,
            model_version=next_version,
            metadata=version_metadata
        )
        
        return next_version
    
    def promote_to_canary(self, model_name: str, version: str, 
                         traffic_percentage: int = 10) -> bool:
        """Promote model to canary stage"""
        try:
            # Transition to canary stage
            self.tracker.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Canary"
            )
            
            # Update metadata
            metadata = {
                'canary_deployment_date': datetime.now().isoformat(),
                'traffic_percentage': traffic_percentage,
                'deployment_type': 'canary'
            }
            
            self.tracker.client.update_model_version(
                name=model_name,
                version=version,
                description=json.dumps(metadata)
            )
            
            return True
        except Exception as e:
            print(f"Error promoting to canary: {e}")
            return False
    
    def promote_to_production(self, model_name: str, version: str, 
                            canary_duration_hours: int = 24) -> bool:
        """Promote model to production after successful canary"""
        try:
            # Archive current production model
            current_prod = self.tracker.get_production_model(model_name)
            if current_prod:
                self.tracker.client.transition_model_version_stage(
                    name=model_name,
                    version=current_prod['version'],
                    stage="Archived"
                )
            
            # Promote new version to production
            self.tracker.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production"
            )
            
            # Create production alias
            self.tracker.create_model_alias(
                model_name=model_name,
                version=version,
                alias="production"
            )
            
            # Update metadata
            metadata = {
                'production_deployment_date': datetime.now().isoformat(),
                'canary_duration_hours': canary_duration_hours,
                'deployment_type': 'production'
            }
            
            self.tracker.client.update_model_version(
                name=model_name,
                version=version,
                description=json.dumps(metadata)
            )
            
            return True
        except Exception as e:
            print(f"Error promoting to production: {e}")
            return False
    
    def rollback_model(self, model_name: str, target_version: Optional[str] = None) -> bool:
        """Rollback to previous stable version"""
        try:
            # Get current production model
            current_prod = self.tracker.get_production_model(model_name)
            if not current_prod:
                print("No production model found to rollback from")
                return False
            
            # If target version not specified, find previous stable version
            if not target_version:
                versions = self.tracker.get_model_versions(model_name)
                
                # Find previous archived or staging version
                for version in versions:
                    if version['version'] != current_prod['version'] and version['stage'] in ["Archived", "Staging"]:
                        target_version = version['version']
                        break
                
                if not target_version:
                    print("No previous version found for rollback")
                    return False
            
            # Archive current production model
            self.tracker.client.transition_model_version_stage(
                name=model_name,
                version=current_prod['version'],
                stage="Staging"  # Move to staging instead of archive for potential reuse
            )
            
            # Promote target version to production
            success = self.tracker.rollback_to_version(model_name, target_version)
            
            if success:
                # Log rollback event
                rollback_metadata = {
                    'rollback_date': datetime.now().isoformat(),
                    'from_version': current_prod['version'],
                    'to_version': target_version,
                    'reason': 'manual_rollback'
                }
                
                # Store rollback metadata
                self.artifact_store.upload_model(
                    model_path="",
                    model_name=model_name,
                    model_version=f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    metadata=rollback_metadata
                )
            
            return success
        except Exception as e:
            print(f"Error during rollback: {e}")
            return False
    
    def get_model_lineage(self, model_name: str) -> Dict[str, Any]:
        """Get model lineage and version history"""
        versions = self.tracker.get_model_versions(model_name)
        
        lineage = {
            'model_name': model_name,
            'total_versions': len(versions),
            'current_production': None,
            'version_history': [],
            'performance_trend': []
        }
        
        # Find current production
        for version in versions:
            if version['stage'] == 'Production':
                lineage['current_production'] = version['version']
        
        # Build version history
        for version in versions:
            run = self.tracker.client.get_run(version['run_id'])
            
            version_info = {
                'version': version['version'],
                'stage': version['stage'],
                'creation_date': version['creation_timestamp'].isoformat(),
                'metrics': run.data.metrics,
                'parameters': run.data.params,
                'description': version['description']
            }
            
            lineage['version_history'].append(version_info)
            
            # Extract performance trend
            if 'f1_score' in run.data.metrics:
                lineage['performance_trend'].append({
                    'version': version['version'],
                    'date': version['creation_timestamp'].isoformat(),
                    'f1_score': run.data.metrics['f1_score']
                })
        
        # Sort by date
        lineage['version_history'].sort(key=lambda x: x['creation_date'], reverse=True)
        lineage['performance_trend'].sort(key=lambda x: x['date'])
        
        return lineage
    
    def cleanup_old_versions(self, model_name: str, keep_versions: int = 5) -> int:
        """Clean up old model versions to save storage"""
        try:
            versions = self.tracker.get_model_versions(model_name)
            
            # Keep production, staging, and canary versions
            protected_versions = []
            cleanup_candidates = []
            
            for version in versions:
                if version['stage'] in ["Production", "Staging", "Canary"]:
                    protected_versions.append(version['version'])
                else:
                    cleanup_candidates.append(version)
            
            # Sort by creation date and keep recent versions
            cleanup_candidates.sort(key=lambda x: x['creation_timestamp'], reverse=True)
            
            versions_to_delete = []
            for i, version in enumerate(cleanup_candidates):
                if i >= keep_versions:
                    versions_to_delete.append(version['version'])
            
            # Delete old versions
            deleted_count = 0
            for version in versions_to_delete:
                # Delete from MLflow
                self.tracker.delete_model_version(model_name, version)
                
                # Delete from MinIO
                self.artifact_store.delete_model(model_name, version)
                
                deleted_count += 1
            
            return deleted_count
        except Exception as e:
            print(f"Error cleaning up old versions: {e}")
            return 0


class RAGModelRegistry(ModelRegistryStrategy):
    """Specialized registry for RAG models"""
    
    def __init__(self):
        super().__init__()
        self.rag_tracker = RAGModelTracker()
        
        # RAG-specific model types
        self.model_types = {
            "embedding": "rag_embedding_model",
            "retrieval": "rag_retrieval_model", 
            "generation": "rag_generation_model",
            "end_to_end": "rag_pipeline_model"
        }
    
    def register_embedding_model(self, run_id: str, metrics: Dict[str, float]) -> str:
        """Register embedding model with RAG-specific logic"""
        metadata = {
            'model_type': 'embedding',
            'task': 'semantic_search',
            'framework': 'sentence-transformers',
            'registration_date': datetime.now().isoformat()
        }
        
        return self.register_new_model(
            model_name=self.model_types["embedding"],
            run_id=run_id,
            metrics=metrics,
            metadata=metadata
        )
    
    def register_retrieval_model(self, run_id: str, metrics: Dict[str, float]) -> str:
        """Register retrieval model"""
        metadata = {
            'model_type': 'retrieval',
            'task': 'document_retrieval',
            'framework': 'llama-index',
            'registration_date': datetime.now().isoformat()
        }
        
        return self.register_new_model(
            model_name=self.model_types["retrieval"],
            run_id=run_id,
            metrics=metrics,
            metadata=metadata
        )
    
    def register_generation_model(self, run_id: str, metrics: Dict[str, float]) -> str:
        """Register generation model"""
        metadata = {
            'model_type': 'generation',
            'task': 'text_generation',
            'framework': 'transformers',
            'registration_date': datetime.now().isoformat()
        }
        
        return self.register_new_model(
            model_name=self.model_types["generation"],
            run_id=run_id,
            metrics=metrics,
            metadata=metadata
        )
    
    def get_rag_pipeline_status(self) -> Dict[str, Any]:
        """Get status of all RAG pipeline models"""
        status = {}
        
        for model_type, model_name in self.model_types.items():
            versions = self.tracker.get_model_versions(model_name)
            production = self.tracker.get_production_model(model_name)
            
            status[model_type] = {
                'model_name': model_name,
                'total_versions': len(versions),
                'current_production': production['version'] if production else None,
                'last_updated': versions[0]['creation_timestamp'].isoformat() if versions else None,
                'stages': {v['version']: v['stage'] for v in versions}
            }
        
        return status
    
    def validate_rag_pipeline(self) -> Dict[str, Any]:
        """Validate that all RAG pipeline components are compatible"""
        validation = {
            'is_valid': True,
            'issues': [],
            'warnings': []
        }
        
        # Check if all model types have production versions
        for model_type, model_name in self.model_types.items():
            production = self.tracker.get_production_model(model_name)
            
            if not production:
                validation['is_valid'] = False
                validation['issues'].append(f"No production version for {model_type} model")
            else:
                # Check if model is recent (within last 30 days)
                age = datetime.now() - production['creation_timestamp']
                if age.days > 30:
                    validation['warnings'].append(f"{model_type} model is {age.days} days old")
        
        return validation
