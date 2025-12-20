# Use Python 3.10-slim for optimal size and performance
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set PYTHONPATH to ensure the application can find the src/ directory
ENV PYTHONPATH=/app/src

# Install system dependencies including audio libraries
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    gcc \
    g++ \
    build-essential \
    pulseaudio-utils \
    libpulse0 \
    ffmpeg \
    curl \
    git \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install uv using pip (most reliable method)
RUN pip install uv

# Copy source code (src/ directory)
COPY src/ src/

# Copy pyproject.toml first for better Docker layer caching
COPY pyproject.toml ./pyproject.toml

# Copy alembic configuration
COPY alembic.ini ./alembic.ini
# Copy alembic migration scripts
COPY alembic/ alembic/

# Copy entrypoint script
COPY docker/stimm/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install the package in development mode
RUN uv sync

# Preload RAG models during Docker build to cache them
# NOTE: Disabled temporarily - default model BAAI/bge-base-en-v1.5 doesn't have pre-converted ONNX version
# Models will be downloaded on first use instead. To enable preloading, use a model with ONNX support
# like sentence-transformers/all-MiniLM-L6-v2 by setting QDRANT_EMBEDDING_MODEL environment variable.
# RUN uv run python src/scripts/preload_rag_models.py

# Expose port
EXPOSE 8001

# Use entrypoint script to run migrations and start server
CMD ["/entrypoint.sh"]