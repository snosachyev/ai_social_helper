"""
MinIO Artifact Storage Integration
"""
from minio import Minio
from minio.error import S3Error
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import tempfile
import shutil
from .config import config


class MinIOArtifactStore:
    """MinIO-based artifact storage for models and datasets"""
    
    def __init__(self):
        self.client = Minio(
            endpoint=config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure
        )
        self.bucket_name = config.minio_bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            print(f"Error creating bucket: {e}")
    
    def upload_model(self, model_path: str, model_name: str, model_version: str, 
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload model artifacts to MinIO"""
        object_name = f"models/{model_name}/{model_version}/model.tar.gz"
        
        # Create metadata
        model_metadata = {
            'model_name': model_name,
            'model_version': model_version,
            'upload_timestamp': datetime.now().isoformat(),
            'file_size': os.path.getsize(model_path) if os.path.isfile(model_path) else 0,
            **(metadata or {})
        }
        
        # Create tar.gz archive
        import tarfile
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
            with tarfile.open(tmp_file.name, 'w:gz') as tar:
                if os.path.isfile(model_path):
                    tar.add(model_path, arcname=os.path.basename(model_path))
                elif os.path.isdir(model_path):
                    for root, dirs, files in os.walk(model_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, model_path)
                            tar.add(file_path, arcname=arcname)
            
            # Upload to MinIO
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=tmp_file.name,
                metadata={
                    'model-metadata': json.dumps(model_metadata)
                }
            )
            
            # Cleanup
            os.unlink(tmp_file.name)
        
        # Upload metadata separately
        metadata_object_name = f"models/{model_name}/{model_version}/metadata.json"
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=metadata_object_name,
            data=json.dumps(model_metadata, indent=2).encode('utf-8'),
            length=len(json.dumps(model_metadata, indent=2)),
            content_type='application/json'
        )
        
        return f"minio://{self.bucket_name}/{object_name}"
    
    def download_model(self, model_name: str, model_version: str, 
                      download_path: str) -> bool:
        """Download model artifacts from MinIO"""
        object_name = f"models/{model_name}/{model_version}/model.tar.gz"
        
        try:
            # Ensure download directory exists
            os.makedirs(download_path, exist_ok=True)
            
            # Download model archive
            temp_file = os.path.join(download_path, 'model.tar.gz')
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=temp_file
            )
            
            # Extract archive
            import tarfile
            with tarfile.open(temp_file, 'r:gz') as tar:
                tar.extractall(download_path)
            
            # Cleanup
            os.unlink(temp_file)
            
            return True
        except S3Error as e:
            print(f"Error downloading model: {e}")
            return False
    
    def upload_dataset(self, dataset_path: str, dataset_name: str, 
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload dataset to MinIO"""
        object_name = f"datasets/{dataset_name}/data.parquet"
        
        # Create metadata
        dataset_metadata = {
            'dataset_name': dataset_name,
            'upload_timestamp': datetime.now().isoformat(),
            'file_size': os.path.getsize(dataset_path),
            **(metadata or {})
        }
        
        # Upload dataset
        self.client.fput_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            file_path=dataset_path,
            metadata={
                'dataset-metadata': json.dumps(dataset_metadata)
            }
        )
        
        # Upload metadata
        metadata_object_name = f"datasets/{dataset_name}/metadata.json"
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=metadata_object_name,
            data=json.dumps(dataset_metadata, indent=2).encode('utf-8'),
            length=len(json.dumps(dataset_metadata, indent=2)),
            content_type='application/json'
        )
        
        return f"minio://{self.bucket_name}/{object_name}"
    
    def download_dataset(self, dataset_name: str, download_path: str) -> bool:
        """Download dataset from MinIO"""
        object_name = f"datasets/{dataset_name}/data.parquet"
        
        try:
            os.makedirs(download_path, exist_ok=True)
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=os.path.join(download_path, 'data.parquet')
            )
            return True
        except S3Error as e:
            print(f"Error downloading dataset: {e}")
            return False
    
    def list_models(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available models"""
        models = []
        
        if model_name:
            prefix = f"models/{model_name}/"
        else:
            prefix = "models/"
        
        objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
        
        model_versions = {}
        for obj in objects:
            if obj.object_name.endswith('/metadata.json'):
                # Extract model info from path
                path_parts = obj.object_name.split('/')
                if len(path_parts) >= 4:
                    model_name = path_parts[1]
                    version = path_parts[2]
                    
                    if model_name not in model_versions:
                        model_versions[model_name] = []
                    
                    # Download and parse metadata
                    try:
                        response = self.client.get_object(self.bucket_name, obj.object_name)
                        metadata = json.loads(response.read().decode('utf-8'))
                        model_versions[model_name].append(metadata)
                    except:
                        pass
        
        return model_versions
    
    def get_model_metadata(self, model_name: str, model_version: str) -> Optional[Dict[str, Any]]:
        """Get model metadata"""
        metadata_object_name = f"models/{model_name}/{model_version}/metadata.json"
        
        try:
            response = self.client.get_object(self.bucket_name, metadata_object_name)
            return json.loads(response.read().decode('utf-8'))
        except S3Error as e:
            print(f"Error getting model metadata: {e}")
            return None
    
    def delete_model(self, model_name: str, model_version: str) -> bool:
        """Delete model artifacts"""
        prefix = f"models/{model_name}/{model_version}/"
        
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            for obj in objects:
                self.client.remove_object(self.bucket_name, obj.object_name)
            return True
        except S3Error as e:
            print(f"Error deleting model: {e}")
            return False
