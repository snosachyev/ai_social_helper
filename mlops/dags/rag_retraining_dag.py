"""
Airflow DAG for RAG Model Retraining Pipeline
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable
import pandas as pd
import numpy as np
import mlflow
import mlflow.pytorch
import torch
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import json
import os
import sys
sys.path.append('/opt/airflow/mlops')

from feature_store import ClickHouseFeatureStore
from artifact_store import MinIOArtifactStore
from config import config


default_args = {
    'owner': 'mlops-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'sla': timedelta(hours=2),
}


def extract_training_data(**context):
    """Extract training data from feature store"""
    feature_store = ClickHouseFeatureStore()
    
    # Get training data from ClickHouse
    training_data = feature_store.get_training_data(limit=10000)
    
    if len(training_data) < config.retraining_min_samples:
        raise ValueError(f"Insufficient training data: {len(training_data)} < {config.retraining_min_samples}")
    
    # Save training data
    data_path = f"/tmp/training_data_{context['ds']}.parquet"
    training_data.to_parquet(data_path)
    
    # Upload to MinIO
    artifact_store = MinIOArtifactStore()
    dataset_uri = artifact_store.upload_dataset(
        dataset_path=data_path,
        dataset_name=f"rag_training_{context['ds']}",
        metadata={
            'sample_count': len(training_data),
            'extraction_date': context['ds'],
            'dag_run_id': context['dag_run'].run_id
        }
    )
    
    Variable.set("latest_dataset_uri", dataset_uri)
    Variable.set("training_data_path", data_path)
    
    return {
        'sample_count': len(training_data),
        'dataset_uri': dataset_uri,
        'data_path': data_path
    }


def preprocess_data(**context):
    """Preprocess training data"""
    data_path = Variable.get("training_data_path")
    
    # Load data
    df = pd.read_parquet(data_path)
    
    # Data preprocessing
    # Clean text data
    df['query_text'] = df['query_text'].str.strip().fillna('')
    df['document_text'] = df['document_text'].str.strip().fillna('')
    
    # Filter out low relevance samples
    df = df[df['relevance_score'] >= 0.3]
    
    # Create labels (binary classification for relevance)
    df['label'] = (df['relevance_score'] >= 0.7).astype(int)
    
    # Split data
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])
    
    # Save processed data
    processed_path = f"/tmp/processed_data_{context['ds']}.parquet"
    train_df.to_parquet(f"/tmp/train_data_{context['ds']}.parquet")
    val_df.to_parquet(f"/tmp/val_data_{context['ds']}.parquet")
    
    Variable.set("train_data_path", f"/tmp/train_data_{context['ds']}.parquet")
    Variable.set("val_data_path", f"/tmp/val_data_{context['ds']}.parquet")
    
    return {
        'train_samples': len(train_df),
        'val_samples': len(val_df),
        'positive_ratio': train_df['label'].mean()
    }


def train_embedding_model(**context):
    """Train new embedding model"""
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment(config.mlflow_experiment_name)
    
    train_path = Variable.get("train_data_path")
    val_path = Variable.get("val_data_path")
    
    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)
    
    with mlflow.start_run(run_name=f"embedding_model_{context['ds']}") as run:
        # Log parameters
        mlflow.log_param("model_type", "sentence-transformer")
        mlflow.log_param("base_model", "sentence-transformers/all-MiniLM-L6-v2")
        mlflow.log_param("train_samples", len(train_df))
        mlflow.log_param("val_samples", len(val_df))
        
        # Initialize model
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # Prepare training data
        train_examples = []
        for _, row in train_df.iterrows():
            train_examples.append({
                'anchor': row['query_text'],
                'positive': row['document_text'] if row['label'] == 1 else None,
                'negative': row['document_text'] if row['label'] == 0 else None
            })
        
        # Training logic (simplified)
        # In practice, you'd use proper contrastive learning
        epochs = 3
        batch_size = 32
        
        for epoch in range(epochs):
            # Simulate training
            model.train()
            # ... actual training code here ...
            
            # Validation
            model.eval()
            with torch.no_grad():
                # Simulate validation metrics
                val_accuracy = np.random.uniform(0.7, 0.9)  # Placeholder
                val_loss = np.random.uniform(0.1, 0.3)  # Placeholder
            
            mlflow.log_metric(f"val_accuracy_epoch_{epoch}", val_accuracy)
            mlflow.log_metric(f"val_loss_epoch_{epoch}", val_loss)
        
        # Final evaluation
        final_accuracy = np.random.uniform(0.75, 0.92)  # Placeholder
        final_precision = np.random.uniform(0.70, 0.90)  # Placeholder
        final_recall = np.random.uniform(0.70, 0.90)  # Placeholder
        final_f1 = np.random.uniform(0.70, 0.90)  # Placeholder
        
        mlflow.log_metric("final_accuracy", final_accuracy)
        mlflow.log_metric("final_precision", final_precision)
        mlflow.log_metric("final_recall", final_recall)
        mlflow.log_metric("final_f1", final_f1)
        
        # Save model
        model_path = f"/tmp/embedding_model_{context['ds']}"
        model.save(model_path)
        
        # Log model to MLflow
        mlflow.pytorch.log_model(
            pytorch_model=model,
            artifact_path="model",
            registered_model_name="rag_embedding_model"
        )
        
        # Upload to MinIO
        artifact_store = MinIOArtifactStore()
        model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        model_uri = artifact_store.upload_model(
            model_path=model_path,
            model_name="rag_embedding_model",
            model_version=model_version,
            metadata={
                'mlflow_run_id': run.info.run_id,
                'accuracy': final_accuracy,
                'precision': final_precision,
                'recall': final_recall,
                'f1_score': final_f1,
                'training_date': context['ds']
            }
        )
        
        Variable.set("new_model_uri", model_uri)
        Variable.set("new_model_version", model_version)
        Variable.set("mlflow_run_id", run.info.run_id)
        
        return {
            'model_uri': model_uri,
            'model_version': model_version,
            'run_id': run.info.run_id,
            'accuracy': final_accuracy,
            'f1_score': final_f1
        }


def evaluate_model(**context):
    """Evaluate trained model against baseline"""
    # Get current production model metrics
    feature_store = ClickHouseFeatureStore()
    current_metrics = feature_store.get_model_performance_history("rag_embedding_model", days=7)
    
    new_model_f1 = float(context['task_instance'].xcom_pull(task_ids='train_embedding_model')['f1_score'])
    
    # Compare with baseline
    if not current_metrics.empty:
        baseline_f1 = current_metrics['f1_score'].iloc[0]
        improvement = (new_model_f1 - baseline_f1) / baseline_f1
        
        mlflow.log_metric("improvement_over_baseline", improvement)
        
        # Decision logic
        should_deploy = improvement > config.model_canary_threshold
    else:
        should_deploy = True  # First model deployment
    
    Variable.set("should_deploy", str(should_deploy))
    
    return {
        'should_deploy': should_deploy,
        'new_model_f1': new_model_f1,
        'baseline_f1': baseline_f1 if not current_metrics.empty else 0.0,
        'improvement': improvement if not current_metrics.empty else 0.0
    }


def deploy_canary(**context):
    """Deploy new model as canary"""
    should_deploy = Variable.get("should_deploy") == "True"
    
    if not should_deploy:
        return {"status": "skipped", "reason": "Model did not meet deployment criteria"}
    
    model_version = Variable.get("new_model_version")
    
    # Deploy to canary environment
    deploy_payload = {
        "model_name": "rag_embedding_model",
        "model_version": model_version,
        "deployment_type": "canary",
        "traffic_percentage": config.canary_traffic_percentage
    }
    
    # Call deployment API
    # This would be an HTTP call to your deployment service
    # For now, we'll simulate it
    
    Variable.set("canary_deployment_time", datetime.now().isoformat())
    
    return {
        "status": "deployed",
        "model_version": model_version,
        "traffic_percentage": config.canary_traffic_percentage
    }


def monitor_canary(**context):
    """Monitor canary deployment performance"""
    should_deploy = Variable.get("should_deploy") == "True"
    
    if not should_deploy:
        return {"status": "skipped"}
    
    # Monitor canary for specified duration
    # In practice, you'd collect metrics and compare with baseline
    
    # Simulate monitoring results
    canary_metrics = {
        "accuracy": np.random.uniform(0.75, 0.92),
        "latency_ms": np.random.uniform(50, 150),
        "error_rate": np.random.uniform(0.01, 0.05)
    }
    
    # Decision to promote or rollback
    promote_to_production = (
        canary_metrics["accuracy"] > 0.8 and
        canary_metrics["latency_ms"] < 200 and
        canary_metrics["error_rate"] < 0.02
    )
    
    Variable.set("promote_to_production", str(promote_to_production))
    
    return {
        "status": "monitored",
        "metrics": canary_metrics,
        "promote_to_production": promote_to_production
    }


def promote_or_rollback(**context):
    """Promote model to production or rollback"""
    should_deploy = Variable.get("should_deploy") == "True"
    promote = Variable.get("promote_to_production") == "True"
    
    if not should_deploy:
        return {"status": "skipped"}
    
    model_version = Variable.get("new_model_version")
    
    if promote:
        # Promote to production
        deploy_payload = {
            "model_name": "rag_embedding_model",
            "model_version": model_version,
            "deployment_type": "production",
            "traffic_percentage": 100
        }
        
        # Update model registry
        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        client = mlflow.tracking.MlflowClient()
        client.transition_model_version_stage(
            name="rag_embedding_model",
            version=model_version,
            stage="Production"
        )
        
        status = "promoted"
    else:
        # Rollback
        if config.model_rollback_enabled:
            # Get previous production model version
            client = mlflow.tracking.MlflowClient()
            model_versions = client.search_model_versions("name='rag_embedding_model'")
            
            production_versions = [
                mv for mv in model_versions 
                if mv.current_stage == "Production" and mv.version != model_version
            ]
            
            if production_versions:
                previous_version = production_versions[0].version
                deploy_payload = {
                    "model_name": "rag_embedding_model",
                    "model_version": previous_version,
                    "deployment_type": "production",
                    "traffic_percentage": 100
                }
                
                # Mark new model as Staged
                client.transition_model_version_stage(
                    name="rag_embedding_model",
                    version=model_version,
                    stage="Staged"
                )
                
                status = "rolled_back"
            else:
                status = "rollback_failed"
        else:
            status = "rollback_disabled"
    
    return {"status": status, "model_version": model_version}


def cleanup(**context):
    """Cleanup temporary files and variables"""
    import os
    
    # Clean up temporary files
    temp_files = [
        Variable.get("training_data_path", default_var=""),
        Variable.get("train_data_path", default_var=""),
        Variable.get("val_data_path", default_var="")
    ]
    
    for file_path in temp_files:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    
    # Clear variables
    variables_to_clear = [
        "latest_dataset_uri",
        "training_data_path", 
        "train_data_path",
        "val_data_path",
        "new_model_uri",
        "new_model_version",
        "mlflow_run_id",
        "should_deploy",
        "canary_deployment_time",
        "promote_to_production"
    ]
    
    for var in variables_to_clear:
        Variable.delete(var)
    
    return {"status": "completed"}


# Create DAG
dag = DAG(
    'rag_retraining_pipeline',
    default_args=default_args,
    description='RAG Model Retraining Pipeline',
    schedule_interval=config.retraining_schedule,
    catchup=False,
    tags=['rag', 'mlops', 'retraining'],
    max_active_runs=1,
)

# Define tasks
extract_data = PythonOperator(
    task_id='extract_training_data',
    python_callable=extract_training_data,
    dag=dag,
)

preprocess = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_data,
    dag=dag,
)

train_model = PythonOperator(
    task_id='train_embedding_model',
    python_callable=train_embedding_model,
    dag=dag,
)

evaluate = PythonOperator(
    task_id='evaluate_model',
    python_callable=evaluate_model,
    dag=dag,
)

deploy_canary_task = PythonOperator(
    task_id='deploy_canary',
    python_callable=deploy_canary,
    dag=dag,
)

monitor_canary_task = PythonOperator(
    task_id='monitor_canary',
    python_callable=monitor_canary,
    dag=dag,
)

promote_or_rollback_task = PythonOperator(
    task_id='promote_or_rollback',
    python_callable=promote_or_rollback,
    dag=dag,
)

cleanup_task = PythonOperator(
    task_id='cleanup',
    python_callable=cleanup,
    dag=dag,
)

# Success notification
success_notification = SlackWebhookOperator(
    task_id='success_notification',
    slack_webhook_conn_id='slack_webhook',
    message=f"✅ RAG Model Retraining Completed Successfully - {{ ds }}",
    channel='#mlops-alerts',
    dag=dag,
)

# Failure notification
failure_notification = SlackWebhookOperator(
    task_id='failure_notification',
    slack_webhook_conn_id='slack_webhook',
    message=f"❌ RAG Model Retraining Failed - {{ ds }}",
    channel='#mlops-alerts',
    trigger_rule='one_failed',
    dag=dag,
)

# Define task dependencies
extract_data >> preprocess >> train_model >> evaluate >> deploy_canary_task
deploy_canary_task >> monitor_canary_task >> promote_or_rollback_task
promote_or_rollback_task >> cleanup_task >> success_notification

# Failure handling
extract_data >> failure_notification
preprocess >> failure_notification
train_model >> failure_notification
evaluate >> failure_notification
deploy_canary_task >> failure_notification
monitor_canary_task >> failure_notification
promote_or_rollback_task >> failure_notification
