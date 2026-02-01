#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER mlflow_user WITH PASSWORD 'mlflow_password';
    CREATE DATABASE mlflow_db;
    GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO mlflow_user;
    
    CREATE USER airflow_user WITH PASSWORD 'airflow_password';
    CREATE DATABASE airflow_db;
    GRANT ALL PRIVILEGES ON DATABASE airflow_db TO airflow_user;
EOSQL
