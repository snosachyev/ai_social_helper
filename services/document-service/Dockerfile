# ---------- base ----------
FROM rag-base-lightweight:latest AS base

WORKDIR /app

# Install only main dependencies
COPY services/document-service/requirements.txt .
RUN grep -v "pytest\|httpx\|aiofiles" requirements.txt > requirements-main.txt \
    && pip install --no-cache-dir -r requirements-main.txt \
    && rm requirements-main.txt requirements.txt

# Copy source code
COPY src/ ./src/
COPY shared/ ./shared/
COPY services/document-service/ .

# ---------- test ----------
FROM base AS test

# Install test dependencies
COPY services/document-service/requirements.txt .
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-mock pytest-cov httpx aiofiles

CMD ["python", "-m", "pytest", "tests/", "-v"]

# ---------- runtime ----------
FROM base AS runtime

# Create entrypoint for permissions
RUN echo '#!/bin/bash\n\
if [ -d "/app/uploads" ]; then\n\
    sudo chown -R app:app /app/uploads 2>/dev/null || true\n\
fi\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

USER root
RUN echo "app ALL=(ALL) NOPASSWD: /bin/chown" >> /etc/sudoers
USER app

ENTRYPOINT ["/app/entrypoint.sh"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
