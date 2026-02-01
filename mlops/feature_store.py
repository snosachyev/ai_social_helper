"""
ClickHouse Feature Store Integration
"""
from clickhouse_driver import Client
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
import json
from .config import config


class ClickHouseFeatureStore:
    """ClickHouse-based feature store for RAG system"""
    
    def __init__(self):
        self.client = Client(
            host=config.clickhouse_host,
            port=config.clickhouse_port,
            database=config.clickhouse_database,
            user=config.clickhouse_user,
            password=config.clickhouse_password
        )
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize ClickHouse database and tables"""
        # Create database if not exists
        self.client.execute(f"CREATE DATABASE IF NOT EXISTS {config.clickhouse_database}")
        
        # Create query features table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS query_features (
                query_id String,
                query_text String,
                embedding Array(Float32),
                timestamp DateTime,
                response_time_ms UInt32,
                relevance_score Float32,
                user_id String,
                session_id String,
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (timestamp, query_id)
        """)
        
        # Create document features table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS document_features (
                document_id String,
                document_text String,
                embedding Array(Float32),
                chunk_count UInt32,
                upload_timestamp DateTime,
                file_type String,
                file_size_bytes UInt64,
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (upload_timestamp, document_id)
        """)
        
        # Create model performance table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                model_name String,
                model_version String,
                timestamp DateTime,
                accuracy Float32,
                precision Float32,
                recall Float32,
                f1_score Float32,
                latency_ms UInt32,
                throughput_qps Float32,
                error_rate Float32,
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (timestamp, model_name, model_version)
        """)
    
    def store_query_features(self, query_data: Dict[str, Any]):
        """Store query-related features"""
        self.client.execute(
            "INSERT INTO query_features VALUES",
            [{
                'query_id': query_data['query_id'],
                'query_text': query_data['query_text'],
                'embedding': query_data['embedding'],
                'timestamp': datetime.now(),
                'response_time_ms': query_data.get('response_time_ms', 0),
                'relevance_score': query_data.get('relevance_score', 0.0),
                'user_id': query_data.get('user_id', ''),
                'session_id': query_data.get('session_id', ''),
                'metadata': json.dumps(query_data.get('metadata', {}))
            }]
        )
    
    def store_document_features(self, doc_data: Dict[str, Any]):
        """Store document-related features"""
        self.client.execute(
            "INSERT INTO document_features VALUES",
            [{
                'document_id': doc_data['document_id'],
                'document_text': doc_data['document_text'],
                'embedding': doc_data['embedding'],
                'chunk_count': doc_data.get('chunk_count', 1),
                'upload_timestamp': datetime.now(),
                'file_type': doc_data.get('file_type', ''),
                'file_size_bytes': doc_data.get('file_size_bytes', 0),
                'metadata': json.dumps(doc_data.get('metadata', {}))
            }]
        )
    
    def store_model_performance(self, perf_data: Dict[str, Any]):
        """Store model performance metrics"""
        self.client.execute(
            "INSERT INTO model_performance VALUES",
            [{
                'model_name': perf_data['model_name'],
                'model_version': perf_data['model_version'],
                'timestamp': datetime.now(),
                'accuracy': perf_data.get('accuracy', 0.0),
                'precision': perf_data.get('precision', 0.0),
                'recall': perf_data.get('recall', 0.0),
                'f1_score': perf_data.get('f1_score', 0.0),
                'latency_ms': perf_data.get('latency_ms', 0),
                'throughput_qps': perf_data.get('throughput_qps', 0.0),
                'error_rate': perf_data.get('error_rate', 0.0),
                'metadata': json.dumps(perf_data.get('metadata', {}))
            }]
        )
    
    def get_training_data(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Retrieve training data from feature store"""
        query = """
            SELECT 
                qf.query_text,
                qf.embedding as query_embedding,
                df.document_text,
                df.embedding as doc_embedding,
                qf.relevance_score
            FROM query_features qf
            JOIN document_features df ON qf.metadata LIKE '%' || df.document_id || '%'
            WHERE qf.timestamp > now() - INTERVAL 30 DAY
            ORDER BY qf.timestamp DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.client.execute_dataframe(query)
    
    def get_model_performance_history(self, model_name: str, days: int = 30) -> pd.DataFrame:
        """Get model performance history"""
        query = f"""
            SELECT *
            FROM model_performance
            WHERE model_name = '{model_name}'
            AND timestamp > now() - INTERVAL {days} DAY
            ORDER BY timestamp DESC
        """
        
        return self.client.execute_dataframe(query)
    
    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get feature store statistics"""
        stats = {}
        
        # Query statistics
        query_stats = self.client.execute("""
            SELECT 
                count() as total_queries,
                avg(response_time_ms) as avg_response_time,
                avg(relevance_score) as avg_relevance_score
            FROM query_features
            WHERE timestamp > now() - INTERVAL 7 DAY
        """)
        
        if query_stats:
            stats['queries'] = {
                'total': query_stats[0][0],
                'avg_response_time_ms': query_stats[0][1],
                'avg_relevance_score': query_stats[0][2]
            }
        
        # Document statistics
        doc_stats = self.client.execute("""
            SELECT 
                count() as total_documents,
                sum(chunk_count) as total_chunks,
                avg(file_size_bytes) as avg_file_size
            FROM document_features
        """)
        
        if doc_stats:
            stats['documents'] = {
                'total': doc_stats[0][0],
                'total_chunks': doc_stats[0][1],
                'avg_file_size_bytes': doc_stats[0][2]
            }
        
        return stats
