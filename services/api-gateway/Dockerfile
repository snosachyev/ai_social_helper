# ---------- base ----------
FROM rag-base-lightweight:latest AS base

WORKDIR /app

# Install service-specific dependencies only
COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared source code, shared modules, and application code
COPY src/ ./src/
COPY shared/ ./shared/
COPY services/api-gateway/ .

# ---------- test ----------
FROM base AS test

# Install test dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-mock pytest-cov httpx

CMD ["pytest", "tests/", "-v"]

# ---------- runtime ----------
FROM base AS runtime

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
