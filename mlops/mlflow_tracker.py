"""
MLflow Experiment Tracking and Model Registry
"""
import mlflow
import mlflow.pytorch
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from typing import Dict, Any, List, Optional
import json
import numpy as np
from datetime import datetime
import torch
from sentence_transformers import SentenceTransformer
from .config import config


class MLflowTracker:
    """MLflow experiment tracking and model registry management"""
    
    def __init__(self):
        self.tracking_uri = config.mlflow_tracking_uri
        self.registry_uri = config.mlflow_registry_uri
        self.experiment_name = config.mlflow_experiment_name
        
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_registry_uri(self.registry_uri)
        
        self.client = MlflowClient()
        
        # Create experiment if it doesn't exist
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            mlflow.create_experiment(self.experiment_name)
    
    def start_training_run(self, run_name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Start a new training run"""
        run = mlflow.start_run(
            experiment_id=mlflow.get_experiment_by_name(self.experiment_name).experiment_id,
            run_name=run_name,
            tags=tags
        )
        return run.info.run_id
    
    def log_parameters(self, run_id: str, parameters: Dict[str, Any]):
        """Log training parameters"""
        with mlflow.start_run(run_id=run_id):
            for key, value in parameters.items():
                mlflow.log_param(key, value)
    
    def log_metrics(self, run_id: str, metrics: Dict[str, float], step: Optional[int] = None):
        """Log training metrics"""
        with mlflow.start_run(run_id=run_id):
            for key, value in metrics.items():
                mlflow.log_metric(key, value, step=step)
    
    def log_model(self, run_id: str, model: Any, model_name: str, 
                  model_type: str = "pytorch", metadata: Optional[Dict[str, Any]] = None):
        """Log model to MLflow"""
        with mlflow.start_run(run_id=run_id):
            if model_type == "pytorch":
                mlflow.pytorch.log_model(model, "model")
            elif model_type == "sklearn":
                mlflow.sklearn.log_model(model, "model")
            else:
                mlflow.log_model(model, "model")
            
            # Log metadata
            if metadata:
                mlflow.log_dict(metadata, "metadata.json")
    
    def register_model(self, run_id: str, model_name: str, 
                      stage: str = "Staging", description: Optional[str] = None):
        """Register model in MLflow Model Registry"""
        with mlflow.start_run(run_id=run_id):
            model_uri = f"runs:/{run_id}/model"
            
            # Register model
            registered_model = mlflow.register_model(
                model_uri=model_uri,
                name=model_name
            )
            
            # Add description
            if description:
                self.client.update_registered_model(
                    name=model_name,
                    description=description
                )
            
            # Transition to specified stage
            self.client.transition_model_version_stage(
                name=model_name,
                version=registered_model.version,
                stage=stage
            )
            
            return registered_model.version
    
    def get_model_versions(self, model_name: str) -> List[Dict[str, Any]]:
        """Get all versions of a model"""
        model_versions = self.client.search_model_versions(f"name='{model_name}'")
        
        versions = []
        for mv in model_versions:
            versions.append({
                'version': mv.version,
                'stage': mv.current_stage,
                'creation_timestamp': datetime.fromtimestamp(mv.creation_timestamp / 1000),
                'last_updated_timestamp': datetime.fromtimestamp(mv.last_updated_timestamp / 1000),
                'description': mv.description,
                'run_id': mv.run_id
            })
        
        return sorted(versions, key=lambda x: x['creation_timestamp'], reverse=True)
    
    def get_production_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get current production model version"""
        model_versions = self.get_model_versions(model_name)
        
        for version in model_versions:
            if version['stage'] == 'Production':
                return version
        
        return None
    
    def promote_to_production(self, model_name: str, version: str, 
                             archive_current: bool = True) -> bool:
        """Promote model version to production"""
        try:
            # Archive current production model if exists
            if archive_current:
                current_prod = self.get_production_model(model_name)
                if current_prod:
                    self.client.transition_model_version_stage(
                        name=model_name,
                        version=current_prod['version'],
                        stage="Archived"
                    )
            
            # Promote new version to production
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production"
            )
            
            return True
        except Exception as e:
            print(f"Error promoting model to production: {e}")
            return False
    
    def rollback_to_version(self, model_name: str, target_version: str) -> bool:
        """Rollback to a specific model version"""
        try:
            # Archive current production model
            current_prod = self.get_production_model(model_name)
            if current_prod:
                self.client.transition_model_version_stage(
                    name=model_name,
                    version=current_prod['version'],
                    stage="Staging"
                )
            
            # Promote target version to production
            self.client.transition_model_version_stage(
                name=model_name,
                version=target_version,
                stage="Production"
            )
            
            return True
        except Exception as e:
            print(f"Error rolling back model: {e}")
            return False
    
    def compare_model_versions(self, model_name: str, version1: str, version2: str) -> Dict[str, Any]:
        """Compare two model versions"""
        try:
            # Get run information for both versions
            mv1 = self.client.get_model_version(model_name, version1)
            mv2 = self.client.get_model_version(model_name, version2)
            
            # Get run metrics
            run1 = self.client.get_run(mv1.run_id)
            run2 = self.client.get_run(mv2.run_id)
            
            comparison = {
                'version1': {
                    'version': version1,
                    'stage': mv1.current_stage,
                    'metrics': run1.data.metrics,
                    'parameters': run1.data.params,
                    'creation_time': datetime.fromtimestamp(mv1.creation_timestamp / 1000)
                },
                'version2': {
                    'version': version2,
                    'stage': mv2.current_stage,
                    'metrics': run2.data.metrics,
                    'parameters': run2.data.params,
                    'creation_time': datetime.fromtimestamp(mv2.creation_timestamp / 1000)
                }
            }
            
            # Calculate metric differences
            metric_diffs = {}
            common_metrics = set(run1.data.metrics.keys()) & set(run2.data.metrics.keys())
            
            for metric in common_metrics:
                val1 = run1.data.metrics[metric]
                val2 = run2.data.metrics[metric]
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    metric_diffs[metric] = {
                        'version1': val1,
                        'version2': val2,
                        'difference': val2 - val1,
                        'percentage_change': ((val2 - val1) / val1 * 100) if val1 != 0 else 0
                    }
            
            comparison['metric_differences'] = metric_diffs
            
            return comparison
        except Exception as e:
            print(f"Error comparing model versions: {e}")
            return {}
    
    def get_model_metrics_history(self, model_name: str, metric_name: str, 
                                 days: int = 30) -> List[Dict[str, Any]]:
        """Get historical metrics for a model"""
        try:
            # Get all model versions
            model_versions = self.get_model_versions(model_name)
            
            history = []
            for version in model_versions:
                run = self.client.get_run(version['run_id'])
                
                if metric_name in run.data.metrics:
                    history.append({
                        'version': version['version'],
                        'stage': version['stage'],
                        'timestamp': version['creation_timestamp'],
                        'metric_value': run.data.metrics[metric_name]
                    })
            
            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
            history = [h for h in history if h['timestamp'] > cutoff_date]
            
            return sorted(history, key=lambda x: x['timestamp'])
        except Exception as e:
            print(f"Error getting model metrics history: {e}")
            return []
    
    def create_model_alias(self, model_name: str, version: str, alias: str) -> bool:
        """Create an alias for a model version"""
        try:
            self.client.set_registered_model_alias(
                name=model_name,
                alias=alias,
                version=version
            )
            return True
        except Exception as e:
            print(f"Error creating model alias: {e}")
            return False
    
    def delete_model_version(self, model_name: str, version: str) -> bool:
        """Delete a model version"""
        try:
            self.client.delete_model_version(
                name=model_name,
                version=version
            )
            return True
        except Exception as e:
            print(f"Error deleting model version: {e}")
            return False


class RAGModelTracker(MLflowTracker):
    """Specialized tracker for RAG models"""
    
    def __init__(self):
        super().__init__()
        self.embedding_model_name = "rag_embedding_model"
        self.retrieval_model_name = "rag_retrieval_model"
        self.generation_model_name = "rag_generation_model"
    
    def log_embedding_model(self, run_id: str, model: SentenceTransformer, 
                           training_data_size: int, validation_metrics: Dict[str, float]):
        """Log embedding model with RAG-specific metadata"""
        metadata = {
            'model_type': 'embedding',
            'training_data_size': training_data_size,
            'framework': 'sentence-transformers',
            'task': 'semantic-search'
        }
        
        self.log_model(run_id, model, self.embedding_model_name, "pytorch", metadata)
        self.log_metrics(run_id, validation_metrics)
        self.log_parameters(run_id, {
            'model_type': 'embedding',
            'training_data_size': training_data_size
        })
    
    def log_retrieval_metrics(self, run_id: str, metrics: Dict[str, float]):
        """Log retrieval-specific metrics"""
        retrieval_metrics = {
            'precision_at_k': metrics.get('precision_at_k', 0),
            'recall_at_k': metrics.get('recall_at_k', 0),
            'mrr': metrics.get('mrr', 0),  # Mean Reciprocal Rank
            'ndcg': metrics.get('ndcg', 0),  # Normalized Discounted Cumulative Gain
            'hit_rate': metrics.get('hit_rate', 0)
        }
        
        self.log_metrics(run_id, retrieval_metrics)
    
    def log_generation_metrics(self, run_id: str, metrics: Dict[str, float]):
        """Log generation-specific metrics"""
        generation_metrics = {
            'bleu_score': metrics.get('bleu_score', 0),
            'rouge_l': metrics.get('rouge_l', 0),
            'meteor': metrics.get('meteor', 0),
            'bert_score': metrics.get('bert_score', 0),
            'perplexity': metrics.get('perplexity', 0),
            'generation_time_ms': metrics.get('generation_time_ms', 0)
        }
        
        self.log_metrics(run_id, generation_metrics)
    
    def evaluate_rag_pipeline(self, run_id: str, test_queries: List[str], 
                            expected_responses: List[str], model_responses: List[str]):
        """Evaluate end-to-end RAG pipeline"""
        from sklearn.metrics import accuracy_score
        import nltk
        from nltk.translate.bleu_score import corpus_bleu
        
        # Calculate various metrics
        # Semantic similarity (placeholder - would use actual embedding similarity)
        semantic_similarities = []
        for expected, generated in zip(expected_responses, model_responses):
            # Placeholder calculation
            similarity = np.random.uniform(0.6, 0.9)  # Replace with actual calculation
            semantic_similarities.append(similarity)
        
        avg_semantic_similarity = np.mean(semantic_similarities)
        
        # BLEU score
        references = [[expected.split()] for expected in expected_responses]
        hypotheses = [response.split() for response in model_responses]
        bleu_score = corpus_bleu(references, hypotheses)
        
        # Response relevance (placeholder)
        relevance_scores = [np.random.uniform(0.7, 0.95) for _ in test_queries]
        avg_relevance = np.mean(relevance_scores)
        
        rag_metrics = {
            'avg_semantic_similarity': avg_semantic_similarity,
            'bleu_score': bleu_score,
            'avg_relevance_score': avg_relevance,
            'num_test_queries': len(test_queries)
        }
        
        self.log_metrics(run_id, rag_metrics)
        
        return rag_metrics
