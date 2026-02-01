# RAG System MLOps

Comprehensive MLOps infrastructure for the RAG system including automated retraining, model registry, canary deployments, and monitoring.

## Architecture Overview

### Core Components

- **MLflow Tracking Server** - Experiment tracking and model registry
- **Apache Airflow** - DAG orchestration for automated pipelines
- **ClickHouse** - Feature store for training data and metrics
- **MinIO** - Artifact storage for models and datasets
- **Canary Deployment** - Safe model deployment with traffic splitting
- **Rollback Mechanism** - Quick rollback to previous stable versions

### Services

- **MLflow Server** (`http://localhost:5000`) - Experiment tracking UI
- **Airflow Webserver** (`http://localhost:8080`) - DAG management
- **MinIO Console** (`http://localhost:9001`) - Object storage UI
- **ClickHouse** (`localhost:9000`) - Feature store database
- **Grafana** (`http://localhost:3001`) - Monitoring dashboards

## Quick Start

### Prerequisites

```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
pip install docker-compose
```

### Start MLOps Infrastructure

```bash
# Start all MLOps services
docker-compose -f docker-compose.mlops.yml up -d

# Check service status
docker-compose -f docker-compose.mlops.yml ps

# View logs
docker-compose -f docker-compose.mlops.yml logs -f mlflow
```

### Initial Setup

1. **Access MLflow**: Open `http://localhost:5000` in your browser
2. **Access Airflow**: Open `http://localhost:8080` (admin/admin)
3. **Access MinIO**: Open `http://localhost:9001` (minioadmin/minioadmin)

## Usage Examples

### 1. Model Training and Registration

```python
from mlops.mlflow_tracker import RAGModelTracker
from mlops.model_registry import RAGModelRegistry

# Initialize tracker and registry
tracker = RAGModelTracker()
registry = RAGModelRegistry()

# Start training run
run_id = tracker.start_training_run("embedding_model_v1")

# Log parameters and metrics
tracker.log_parameters(run_id, {
    "model_type": "embedding",
    "batch_size": 32,
    "learning_rate": 0.001
})

tracker.log_metrics(run_id, {
    "accuracy": 0.85,
    "f1_score": 0.82,
    "precision": 0.84,
    "recall": 0.80
})

# Register model
version = registry.register_embedding_model(run_id, {
    "accuracy": 0.85,
    "f1_score": 0.82
})

print(f"Model registered as version: {version}")
```

### 2. Canary Deployment

```python
from mlops.deployment import CanaryDeployment, DeploymentConfig
import asyncio

# Initialize deployment manager
deployment = CanaryDeployment()

# Configure canary deployment
config = DeploymentConfig(
    model_name="rag_embedding_model",
    model_version="1.2.3",
    deployment_type="canary",
    traffic_percentage=10,
    canary_duration=3600  # 1 hour
)

# Deploy canary
async def deploy_canary():
    result = await deployment.deploy_canary(config)
    print(f"Canary deployment: {result}")

# Run deployment
asyncio.run(deploy_canary())
```

### 3. Feature Store Operations

```python
from mlops.feature_store import ClickHouseFeatureStore

# Initialize feature store
feature_store = ClickHouseFeatureStore()

# Store query features
feature_store.store_query_features({
    "query_id": "q123",
    "query_text": "What is machine learning?",
    "embedding": [0.1, 0.2, 0.3, ...],
    "response_time_ms": 150,
    "relevance_score": 0.85,
    "user_id": "user456",
    "session_id": "session789"
})

# Get training data
training_data = feature_store.get_training_data(limit=10000)
print(f"Retrieved {len(training_data)} training samples")

# Get model performance history
performance = feature_store.get_model_performance_history(
    "rag_embedding_model", 
    days=30
)
```

### 4. Artifact Storage

```python
from mlops.artifact_store import MinIOArtifactStore

# Initialize artifact store
artifact_store = MinIOArtifactStore()

# Upload model
model_uri = artifact_store.upload_model(
    model_path="/path/to/model",
    model_name="rag_embedding_model",
    model_version="1.2.3",
    metadata={
        "accuracy": 0.85,
        "training_date": "2024-01-15"
    }
)

# Download model
success = artifact_store.download_model(
    model_name="rag_embedding_model",
    model_version="1.2.3",
    download_path="/tmp/downloaded_model"
)

# List available models
models = artifact_store.list_models("rag_embedding_model")
```

### 5. Rollback Operations

```python
from mlops.deployment import RollbackManager
import asyncio

# Initialize rollback manager
rollback_manager = RollbackManager()

# Emergency rollback
async def emergency_rollback():
    result = await rollback_manager.emergency_rollback(
        model_name="rag_embedding_model",
        reason="High error rate detected"
    )
    print(f"Rollback result: {result}")

asyncio.run(emergency_rollback())
```

## Airflow DAGs

### RAG Retraining Pipeline

The `rag_retraining_dag.py` provides automated model retraining:

1. **Data Extraction** - Pull training data from ClickHouse feature store
2. **Preprocessing** - Clean and prepare training data
3. **Model Training** - Train new embedding model
4. **Evaluation** - Compare against baseline metrics
5. **Canary Deployment** - Deploy as canary with traffic splitting
6. **Monitoring** - Monitor canary performance
7. **Promotion/Rollback** - Promote to production or rollback

### Model Monitoring DAG

The `model_monitoring_dag.py` provides continuous monitoring:

1. **Metrics Collection** - Collect performance metrics from production
2. **Anomaly Detection** - Detect performance anomalies
3. **Data Drift Detection** - Monitor input data distribution
4. **Alert Generation** - Generate alerts for issues
5. **Dashboard Updates** - Update monitoring dashboards

## Configuration

### Environment Variables

Create a `.env` file in the `mlops` directory:

```env
# MLflow Configuration
MLOPS_MLFLOW_TRACKING_URI=http://localhost:5000
MLOPS_MLFLOW_EXPERIMENT_NAME=rag_retraining
MLOPS_MLFLOW_REGISTRY_URI=http://localhost:5000

# ClickHouse Configuration
MLOPS_CLICKHOUSE_HOST=localhost
MLOPS_CLICKHOUSE_PORT=9000
MLOPS_CLICKHOUSE_DATABASE=rag_features
MLOPS_CLICKHOUSE_USER=default
MLOPS_CLICKHOUSE_PASSWORD=

# MinIO Configuration
MLOPS_MINIO_ENDPOINT=localhost:9000
MLOPS_MINIO_ACCESS_KEY=minioadmin
MLOPS_MINIO_SECRET_KEY=minioadmin
MLOPS_MINIO_BUCKET_NAME=rag-artifacts
MLOPS_MINIO_SECURE=false

# Model Registry Configuration
MLOPS_MODEL_REGISTRY_STAGE=Production
MLOPS_MODEL_CANARY_THRESHOLD=0.05
MLOPS_MODEL_ROLLBACK_ENABLED=true

# Retraining Configuration
MLOPS_RETRAINING_SCHEDULE=@daily
MLOPS_RETRAINING_DATA_PATH=/data/retraining
MLOPS_RETRAINING_MIN_SAMPLES=100

# Deployment Configuration
MLOPS_DEPLOYMENT_STRATEGY=canary
MLOPS_CANARY_TRAFFIC_PERCENTAGE=10
MLOPS_ROLLBACK_TIMEOUT_MINUTES=30
```

## Monitoring

### Grafana Dashboards

Access Grafana at `http://localhost:3001` (admin/admin):

- **Model Performance** - Track model accuracy, latency, and error rates
- **Training Pipeline** - Monitor DAG runs and training metrics
- **Feature Store** - Query patterns and data quality metrics
- **System Health** - Resource usage and service health

### Key Metrics

- **Model Accuracy** - F1 score, precision, recall
- **Latency** - P50, P95, P99 response times
- **Error Rate** - Failed requests percentage
- **Throughput** - Queries per second
- **Data Quality** - Feature distribution and drift

## Best Practices

### Model Versioning

1. **Semantic Versioning** - Use major.minor.patch based on performance improvements
2. **Automated Promotion** - Promote only after successful canary deployment
3. **Rollback Strategy** - Always keep previous stable version available

### Canary Deployments

1. **Start Small** - Begin with 5-10% traffic
2. **Monitor Closely** - Track key metrics during canary period
3. **Quick Rollback** - Set up automated rollback triggers

### Feature Store

1. **Data Quality** - Validate input data before storage
2. **Retention Policy** - Archive old data to manage storage costs
3. **Access Control** - Implement proper data access controls

## Troubleshooting

### Common Issues

1. **MLflow Connection Issues**
   ```bash
   # Check MLflow server status
   docker-compose -f docker-compose.mlops.yml logs mlflow
   
   # Verify database connection
   docker-compose -f docker-compose.mlops.yml exec postgres psql -U mlflow_user -d mlflow_db
   ```

2. **Airflow DAG Not Running**
   ```bash
   # Check Airflow scheduler logs
   docker-compose -f docker-compose.mlops.yml logs airflow-scheduler
   
   # Unpause DAG
   docker-compose -f docker-compose.mlops.yml exec airflow-webserver airflow dags unpause rag_retraining_pipeline
   ```

3. **ClickHouse Connection Issues**
   ```bash
   # Check ClickHouse status
   docker-compose -f docker-compose.mlops.yml logs clickhouse
   
   # Test connection
   docker-compose -f docker-compose.mlops.yml exec clickhouse clickhouse-client --query "SELECT 1"
   ```

4. **MinIO Storage Issues**
   ```bash
   # Check MinIO status
   docker-compose -f docker-compose.mlops.yml logs minio
   
   # Verify bucket creation
   docker-compose -f docker-compose.mlops.yml exec mc mc ls myminio/
   ```

### Health Checks

```bash
# Check all services
docker-compose -f docker-compose.mlops.yml ps

# Check service health
curl http://localhost:5000/health  # MLflow
curl http://localhost:8080/health  # Airflow
curl http://localhost:8123/ping   # ClickHouse
curl http://localhost:9000/minio/health/live  # MinIO
```

## Development

### Running Tests

```bash
# Install dependencies
pip install -r mlops/requirements.txt

# Run tests
python -m pytest mlops/tests/

# Run with coverage
python -m pytest mlops/tests/ --cov=mlops
```

### Code Quality

```bash
# Format code
black mlops/

# Lint code
flake8 mlops/

# Type checking
mypy mlops/
```

## Security Considerations

1. **Secret Management** - Use environment variables for sensitive data
2. **Network Security** - Implement proper firewall rules
3. **Access Control** - Configure RBAC for all services
4. **Data Encryption** - Enable encryption for data at rest and in transit

## Scaling

### Horizontal Scaling

```bash
# Scale Airflow workers
docker-compose -f docker-compose.mlops.yml up --scale airflow-worker=3

# Scale ClickHouse cluster
# Update configuration for multi-node setup
```

### Resource Optimization

1. **Model Caching** - Cache frequently used models in memory
2. **Batch Processing** - Use batch processing for feature extraction
3. **Storage Optimization** - Compress model artifacts and use lifecycle policies

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review service logs
3. Create an issue in the repository
4. Contact the MLOps team
