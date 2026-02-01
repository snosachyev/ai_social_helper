# Model service - ML heavy
FROM rag-base-ml-cpu:latest

# Install service-specific dependencies only
COPY services/model-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared source code, shared modules, and application code
COPY src/ ./src/
COPY shared/ ./shared/
COPY services/model-service/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1

EXPOSE 8006
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
