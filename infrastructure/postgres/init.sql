-- Create additional databases
CREATE DATABASE mlflow;
CREATE DATABASE airflow;

-- Create user for applications
CREATE USER rag_user WITH PASSWORD 'rag_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE rag_db TO rag_user;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO rag_user;
GRANT ALL PRIVILEGES ON DATABASE airflow TO rag_user;

-- Connect to mlflow database and grant schema privileges
\c mlflow;
GRANT ALL ON SCHEMA public TO rag_user;

-- Connect to airflow database and grant schema privileges  
\c airflow;
GRANT ALL ON SCHEMA public TO rag_user;
