#!/usr/bin/env python3
"""
Basic usage examples for RAG MLOps components
"""
import asyncio
import numpy as np
from datetime import datetime

# Import MLOps components
from mlops.feature_store import ClickHouseFeatureStore
from mlops.artifact_store import MinIOArtifactStore
from mlops.mlflow_tracker import RAGModelTracker
from mlops.model_registry import RAGModelRegistry
from mlops.deployment import CanaryDeployment, DeploymentConfig, RollbackManager
from mlops.config import config


def demonstrate_feature_store():
    """Demonstrate feature store operations"""
    print("=== Feature Store Demo ===")
    
    # Initialize feature store
    feature_store = ClickHouseFeatureStore()
    
    # Store sample query features
    query_data = {
        "query_id": f"query_{datetime.now().timestamp()}",
        "query_text": "What is the difference between supervised and unsupervised learning?",
        "embedding": np.random.rand(384).tolist(),  # Sample embedding
        "response_time_ms": 150,
        "relevance_score": 0.85,
        "user_id": "user123",
        "session_id": "session456",
        "metadata": {"model_version": "1.0.0", "source": "web"}
    }
    
    feature_store.store_query_features(query_data)
    print(f"✅ Stored query features for: {query_data['query_text'][:50]}...")
    
    # Store sample document features
    doc_data = {
        "document_id": f"doc_{datetime.now().timestamp()}",
        "document_text": "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data...",
        "embedding": np.random.rand(384).tolist(),
        "chunk_count": 5,
        "upload_timestamp": datetime.now(),
        "file_type": "pdf",
        "file_size_bytes": 1024000,
        "metadata": {"source": "upload", "category": "ml_basics"}
    }
    
    feature_store.store_document_features(doc_data)
    print(f"✅ Stored document features: {doc_data['document_text'][:50]}...")
    
    # Store model performance
    perf_data = {
        "model_name": "rag_embedding_model",
        "model_version": "1.0.0",
        "accuracy": 0.85,
        "precision": 0.84,
        "recall": 0.86,
        "f1_score": 0.85,
        "latency_ms": 120,
        "throughput_qps": 25.5,
        "error_rate": 0.02,
        "metadata": {"test_dataset": "validation_set_v2"}
    }
    
    feature_store.store_model_performance(perf_data)
    print(f"✅ Stored model performance for {perf_data['model_name']} v{perf_data['model_version']}")
    
    # Get feature statistics
    stats = feature_store.get_feature_statistics()
    print(f"📊 Feature store stats: {stats}")
    
    return feature_store


def demonstrate_artifact_store():
    """Demonstrate artifact storage operations"""
    print("\n=== Artifact Store Demo ===")
    
    # Initialize artifact store
    artifact_store = MinIOArtifactStore()
    
    # Create a dummy model file
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a sample model file for demonstration purposes.\n")
        f.write("Model weights and configuration would be stored here.\n")
        model_path = f.name
    
    try:
        # Upload model
        model_uri = artifact_store.upload_model(
            model_path=model_path,
            model_name="demo_embedding_model",
            model_version="1.0.0",
            metadata={
                "accuracy": 0.85,
                "training_date": datetime.now().isoformat(),
                "framework": "sentence-transformers"
            }
        )
        print(f"✅ Uploaded model to: {model_uri}")
        
        # List models
        models = artifact_store.list_models("demo_embedding_model")
        print(f"📋 Available models: {len(models)} versions")
        
        # Get model metadata
        metadata = artifact_store.get_model_metadata("demo_embedding_model", "1.0.0")
        print(f"📄 Model metadata: {metadata}")
        
    finally:
        # Cleanup
        os.unlink(model_path)
    
    return artifact_store


def demonstrate_mlflow_tracking():
    """Demonstrate MLflow experiment tracking"""
    print("\n=== MLflow Tracking Demo ===")
    
    # Initialize tracker
    tracker = RAGModelTracker()
    
    # Start a training run
    run_name = f"demo_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_id = tracker.start_training_run(run_name, tags={"demo": "true", "model_type": "embedding"})
    print(f"🚀 Started training run: {run_id}")
    
    # Log parameters
    parameters = {
        "model_type": "sentence-transformer",
        "base_model": "all-MiniLM-L6-v2",
        "batch_size": 32,
        "learning_rate": 0.001,
        "epochs": 3,
        "max_seq_length": 512
    }
    
    tracker.log_parameters(run_id, parameters)
    print(f"📝 Logged {len(parameters)} parameters")
    
    # Log metrics (simulated training progress)
    for epoch in range(3):
        metrics = {
            "train_loss": np.random.uniform(0.1, 0.5),
            "val_loss": np.random.uniform(0.15, 0.4),
            "accuracy": np.random.uniform(0.7, 0.9),
            "f1_score": np.random.uniform(0.75, 0.85)
        }
        
        tracker.log_metrics(run_id, metrics, step=epoch)
        print(f"📊 Epoch {epoch + 1}: accuracy={metrics['accuracy']:.3f}, f1={metrics['f1_score']:.3f}")
    
    # Log final metrics
    final_metrics = {
        "final_accuracy": 0.85,
        "final_precision": 0.84,
        "final_recall": 0.86,
        "final_f1_score": 0.85
    }
    
    tracker.log_metrics(run_id, final_metrics)
    print(f"✅ Logged final metrics: {final_metrics}")
    
    return tracker, run_id


def demonstrate_model_registry(tracker, run_id):
    """Demonstrate model registry operations"""
    print("\n=== Model Registry Demo ===")
    
    # Initialize registry
    registry = RAGModelRegistry()
    
    # Register embedding model
    metrics = {
        "accuracy": 0.85,
        "precision": 0.84,
        "recall": 0.86,
        "f1_score": 0.85
    }
    
    version = registry.register_embedding_model(run_id, metrics)
    print(f"📦 Registered embedding model as version: {version}")
    
    # Get model lineage
    lineage = registry.get_model_lineage("rag_embedding_model")
    print(f"🌳 Model lineage: {lineage['total_versions']} versions")
    
    # Get RAG pipeline status
    pipeline_status = registry.get_rag_pipeline_status()
    print(f"🔄 RAG pipeline status: {list(pipeline_status.keys())}")
    
    # Validate RAG pipeline
    validation = registry.validate_rag_pipeline()
    print(f"✅ Pipeline validation: {'Valid' if validation['is_valid'] else 'Invalid'}")
    
    return registry


async def demonstrate_deployment():
    """Demonstrate canary deployment"""
    print("\n=== Canary Deployment Demo ===")
    
    # Initialize deployment manager
    deployment = CanaryDeployment()
    
    # Configure canary deployment
    config = DeploymentConfig(
        model_name="rag_embedding_model",
        model_version="1.0.0",
        deployment_type="canary",
        traffic_percentage=10,
        health_check_interval=30,
        canary_duration=300  # 5 minutes for demo
    )
    
    print(f"🚀 Configuring canary deployment: {config.model_name}:{config.model_version}")
    print(f"📊 Traffic percentage: {config.traffic_percentage}%")
    
    # Note: In a real environment, this would deploy to actual services
    # For demo purposes, we'll just show the configuration
    print(f"⚠️  Demo mode: Would deploy canary with config:")
    print(f"   - Model: {config.model_name}")
    print(f"   - Version: {config.model_version}")
    print(f"   - Traffic: {config.traffic_percentage}%")
    print(f"   - Duration: {config.canary_duration}s")
    
    return deployment


async def demonstrate_rollback():
    """Demonstrate rollback operations"""
    print("\n=== Rollback Demo ===")
    
    # Initialize rollback manager
    rollback_manager = RollbackManager()
    
    print(f"🔄 Rollback manager initialized")
    print(f"⚠️  Demo mode: Would perform emergency rollback if needed")
    
    # Get rollback history (demo)
    history = rollback_manager.get_rollback_history("rag_embedding_model")
    print(f"📚 Rollback history: {len(history)} events")
    
    return rollback_manager


def main():
    """Run all demonstrations"""
    print("🎯 RAG MLOps Demonstration")
    print("=" * 50)
    
    try:
        # Feature Store Demo
        feature_store = demonstrate_feature_store()
        
        # Artifact Store Demo
        artifact_store = demonstrate_artifact_store()
        
        # MLflow Tracking Demo
        tracker, run_id = demonstrate_mlflow_tracking()
        
        # Model Registry Demo
        registry = demonstrate_model_registry(tracker, run_id)
        
        # Deployment Demo (async)
        asyncio.run(demonstrate_deployment())
        
        # Rollback Demo (async)
        asyncio.run(demonstrate_rollback())
        
        print("\n" + "=" * 50)
        print("✅ All demonstrations completed successfully!")
        print("\n📚 Next Steps:")
        print("1. Start the MLOps infrastructure: docker-compose -f docker-compose.mlops.yml up -d")
        print("2. Access MLflow UI: http://localhost:5000")
        print("3. Access Airflow UI: http://localhost:8080")
        print("4. Access MinIO Console: http://localhost:9001")
        print("5. Check the examples in mlops/examples/ for more detailed usage")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure all MLOps services are running")
        print("2. Check service logs: docker-compose -f docker-compose.mlops.yml logs")
        print("3. Verify configuration in mlops/config.py")


if __name__ == "__main__":
    main()
