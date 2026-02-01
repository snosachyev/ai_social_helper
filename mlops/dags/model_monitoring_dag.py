"""
Airflow DAG for Continuous Model Monitoring
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.operators.email import EmailOperator
import pandas as pd
import numpy as np
import mlflow
import json
import sys
sys.path.append('/opt/airflow/mlops')

from feature_store import ClickHouseFeatureStore
from config import config


default_args = {
    'owner': 'mlops-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def collect_model_metrics(**context):
    """Collect model performance metrics from production"""
    feature_store = ClickHouseFeatureStore()
    
    # Get metrics for the last hour
    metrics_data = feature_store.client.execute("""
        SELECT 
            model_name,
            model_version,
            count() as query_count,
            avg(response_time_ms) as avg_response_time,
            quantile(0.95)(response_time_ms) as p95_response_time,
            avg(relevance_score) as avg_relevance_score,
            countIf(response_time_ms > 1000) as slow_queries,
            countIf(relevance_score < 0.5) as poor_relevance_queries
        FROM query_features
        WHERE timestamp > now() - INTERVAL 1 HOUR
        GROUP BY model_name, model_version
    """)
    
    metrics_list = []
    for row in metrics_data:
        metrics_list.append({
            'model_name': row[0],
            'model_version': row[1],
            'query_count': row[2],
            'avg_response_time_ms': row[3],
            'p95_response_time_ms': row[4],
            'avg_relevance_score': row[5],
            'slow_queries': row[6],
            'poor_relevance_queries': row[7],
            'slow_query_rate': row[6] / row[2] if row[2] > 0 else 0,
            'poor_relevance_rate': row[7] / row[2] if row[2] > 0 else 0,
            'timestamp': datetime.now().isoformat()
        })
    
    # Store metrics in ClickHouse for historical tracking
    for metrics in metrics_list:
        feature_store.store_model_performance({
            'model_name': metrics['model_name'],
            'model_version': metrics['model_version'],
            'accuracy': metrics['avg_relevance_score'],
            'precision': 1.0 - metrics['poor_relevance_rate'],
            'recall': 1.0 - metrics['poor_relevance_rate'],
            'f1_score': 1.0 - metrics['poor_relevance_rate'],
            'latency_ms': metrics['avg_response_time_ms'],
            'throughput_qps': metrics['query_count'] / 3600,  # queries per second
            'error_rate': metrics['slow_query_rate'],
            'metadata': json.dumps({
                'p95_response_time_ms': metrics['p95_response_time_ms'],
                'query_count': metrics['query_count']
            })
        })
    
    return {
        'metrics_count': len(metrics_list),
        'metrics': metrics_list
    }


def detect_anomalies(**context):
    """Detect anomalies in model performance"""
    feature_store = ClickHouseFeatureStore()
    
    # Get recent metrics for comparison
    recent_metrics = feature_store.client.execute("""
        SELECT 
            model_name,
            model_version,
            timestamp,
            accuracy,
            latency_ms,
            error_rate,
            throughput_qps
        FROM model_performance
        WHERE timestamp > now() - INTERVAL 24 HOUR
        ORDER BY timestamp DESC
    """)
    
    anomalies = []
    
    # Group by model and version
    model_data = {}
    for row in recent_metrics:
        key = f"{row[0]}_{row[1]}"
        if key not in model_data:
            model_data[key] = []
        model_data[key].append({
            'timestamp': row[2],
            'accuracy': row[3],
            'latency_ms': row[4],
            'error_rate': row[5],
            'throughput_qps': row[6]
        })
    
    # Detect anomalies for each model
    for model_key, metrics in model_data.items():
        if len(metrics) < 10:  # Need sufficient data
            continue
        
        # Calculate baseline (excluding most recent)
        baseline = metrics[:-5]
        recent = metrics[-5:]
        
        baseline_accuracy = np.mean([m['accuracy'] for m in baseline])
        baseline_latency = np.mean([m['latency_ms'] for m in baseline])
        baseline_error_rate = np.mean([m['error_rate'] for m in baseline])
        
        recent_accuracy = np.mean([m['accuracy'] for m in recent])
        recent_latency = np.mean([m['latency_ms'] for m in recent])
        recent_error_rate = np.mean([m['error_rate'] for m in recent])
        
        # Check for anomalies
        accuracy_drop = (baseline_accuracy - recent_accuracy) / baseline_accuracy
        latency_increase = (recent_latency - baseline_latency) / baseline_latency
        error_increase = (recent_error_rate - baseline_error_rate) / baseline_error_rate
        
        if accuracy_drop > 0.1:  # 10% drop in accuracy
            anomalies.append({
                'model': model_key,
                'type': 'accuracy_drop',
                'severity': 'high' if accuracy_drop > 0.2 else 'medium',
                'value': accuracy_drop,
                'threshold': 0.1
            })
        
        if latency_increase > 0.3:  # 30% increase in latency
            anomalies.append({
                'model': model_key,
                'type': 'latency_increase',
                'severity': 'high' if latency_increase > 0.5 else 'medium',
                'value': latency_increase,
                'threshold': 0.3
            })
        
        if error_increase > 0.5:  # 50% increase in error rate
            anomalies.append({
                'model': model_key,
                'type': 'error_rate_increase',
                'severity': 'high' if error_increase > 1.0 else 'medium',
                'value': error_increase,
                'threshold': 0.5
            })
    
    return {
        'anomaly_count': len(anomalies),
        'anomalies': anomalies
    }


def check_data_drift(**context):
    """Check for data drift in input features"""
    feature_store = ClickHouseFeatureStore()
    
    # Get current query statistics
    current_stats = feature_store.client.execute("""
        SELECT 
            avg(length(query_text)) as avg_query_length,
            quantile(0.5)(length(query_text)) as median_query_length,
            quantile(0.95)(length(query_text)) as p95_query_length,
            count(DISTINCT user_id) as unique_users,
            count(DISTINCT session_id) as unique_sessions
        FROM query_features
        WHERE timestamp > now() - INTERVAL 1 HOUR
    """)
    
    # Get historical statistics for comparison
    historical_stats = feature_store.client.execute("""
        SELECT 
            avg(length(query_text)) as avg_query_length,
            quantile(0.5)(length(query_text)) as median_query_length,
            quantile(0.95)(length(query_text)) as p95_query_length,
            count(DISTINCT user_id) as unique_users,
            count(DISTINCT session_id) as unique_sessions
        FROM query_features
        WHERE timestamp BETWEEN now() - INTERVAL 7 DAY AND now() - INTERVAL 1 HOUR
    """)
    
    if not current_stats or not historical_stats:
        return {'status': 'insufficient_data'}
    
    current = current_stats[0]
    historical = historical_stats[0]
    
    drift_indicators = []
    
    # Check query length drift
    query_length_drift = abs(current[0] - historical[0]) / historical[0] if historical[0] > 0 else 0
    if query_length_drift > 0.2:
        drift_indicators.append({
            'type': 'query_length_drift',
            'severity': 'medium',
            'current': current[0],
            'historical': historical[0],
            'drift_percentage': query_length_drift
        })
    
    # Check user behavior drift
    user_drift = abs(current[3] - historical[3]) / historical[3] if historical[3] > 0 else 0
    if user_drift > 0.5:
        drift_indicators.append({
            'type': 'user_count_drift',
            'severity': 'low',
            'current': current[3],
            'historical': historical[3],
            'drift_percentage': user_drift
        })
    
    return {
        'drift_count': len(drift_indicators),
        'drift_indicators': drift_indicators,
        'current_stats': {
            'avg_query_length': current[0],
            'unique_users': current[3],
            'unique_sessions': current[4]
        },
        'historical_stats': {
            'avg_query_length': historical[0],
            'unique_users': historical[3],
            'unique_sessions': historical[4]
        }
    }


def generate_alerts(**context):
    """Generate alerts for anomalies and drift"""
    anomalies = context['task_instance'].xcom_pull(task_ids='detect_anomalies')
    drift = context['task_instance'].xcom_pull(task_ids='check_data_drift')
    
    alerts = []
    
    # Process anomalies
    for anomaly in anomalies.get('anomalies', []):
        alert = {
            'type': 'model_performance',
            'severity': anomaly['severity'],
            'model': anomaly['model'],
            'issue': anomaly['type'],
            'value': anomaly['value'],
            'threshold': anomaly['threshold'],
            'timestamp': datetime.now().isoformat()
        }
        alerts.append(alert)
    
    # Process drift indicators
    for drift_indicator in drift.get('drift_indicators', []):
        alert = {
            'type': 'data_drift',
            'severity': drift_indicator['severity'],
            'issue': drift_indicator['type'],
            'current': drift_indicator['current'],
            'historical': drift_indicator['historical'],
            'drift_percentage': drift_indicator['drift_percentage'],
            'timestamp': datetime.now().isoformat()
        }
        alerts.append(alert)
    
    # Store alerts in ClickHouse
    feature_store = ClickHouseFeatureStore()
    
    # Create alerts table if not exists
    feature_store.client.execute("""
        CREATE TABLE IF NOT EXISTS model_alerts (
            alert_id String,
            alert_type String,
            severity String,
            model_name String,
            issue String,
            details String,
            timestamp DateTime,
            resolved Bool DEFAULT false
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, alert_id)
    """)
    
    for alert in alerts:
        feature_store.client.execute(
            "INSERT INTO model_alerts VALUES",
            [{
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(alerts)}",
                'alert_type': alert['type'],
                'severity': alert['severity'],
                'model_name': alert.get('model', 'unknown'),
                'issue': alert['issue'],
                'details': json.dumps(alert),
                'timestamp': datetime.now(),
                'resolved': False
            }]
        )
    
    return {
        'alert_count': len(alerts),
        'alerts': alerts,
        'high_severity_count': len([a for a in alerts if a['severity'] == 'high'])
    }


def create_dashboard_update(**context):
    """Update monitoring dashboard with latest metrics"""
    metrics = context['task_instance'].xcom_pull(task_ids='collect_model_metrics')
    anomalies = context['task_instance'].xcom_pull(task_ids='detect_anomalies')
    alerts = context['task_instance'].xcom_pull(task_ids='generate_alerts')
    
    dashboard_data = {
        'last_updated': datetime.now().isoformat(),
        'metrics': metrics,
        'anomalies': anomalies,
        'alerts': alerts,
        'status': 'healthy' if alerts.get('high_severity_count', 0) == 0 else 'warning'
    }
    
    # Save dashboard data
    dashboard_path = f"/tmp/dashboard_data_{context['ds']}.json"
    with open(dashboard_path, 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    return {
        'dashboard_path': dashboard_path,
        'status': dashboard_data['status'],
        'high_severity_alerts': alerts.get('high_severity_count', 0)
    }


# Create DAG
dag = DAG(
    'model_monitoring',
    default_args=default_args,
    description='Continuous Model Monitoring and Alerting',
    schedule_interval='@hourly',
    catchup=False,
    tags=['rag', 'mlops', 'monitoring'],
    max_active_runs=1,
)

# Define tasks
collect_metrics = PythonOperator(
    task_id='collect_model_metrics',
    python_callable=collect_model_metrics,
    dag=dag,
)

detect_anomalies_task = PythonOperator(
    task_id='detect_anomalies',
    python_callable=detect_anomalies,
    dag=dag,
)

check_drift = PythonOperator(
    task_id='check_data_drift',
    python_callable=check_data_drift,
    dag=dag,
)

generate_alerts_task = PythonOperator(
    task_id='generate_alerts',
    python_callable=generate_alerts,
    dag=dag,
)

update_dashboard = PythonOperator(
    task_id='update_dashboard',
    python_callable=create_dashboard_update,
    dag=dag,
)

# Alert notifications
high_severity_alert = EmailOperator(
    task_id='high_severity_alert',
    to='mlops-team@company.com',
    subject='🚨 High Severity Model Alert Detected',
    html_content="""
    <h2>High Severity Model Alert</h2>
    <p>High severity alerts have been detected in the RAG model monitoring system.</p>
    <p>Please check the monitoring dashboard for details.</p>
    <p>Time: {{ ds }}</p>
    """,
    trigger_rule='one_success',
    dag=dag,
)

# Define task dependencies
collect_metrics >> [detect_anomalies_task, check_drift]
detect_anomalies_task >> generate_alerts_task
check_drift >> generate_alerts_task
generate_alerts_task >> update_dashboard

# Conditional alert for high severity issues
update_dashboard >> high_severity_alert
