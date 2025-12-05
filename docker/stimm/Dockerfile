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
    && rm -rf /var/lib/apt/lists/*

# Install uv using pip (most reliable method)
RUN pip install uv

# Copy source code (src/ directory)
COPY src/ src/

# Copy pyproject.toml first for better Docker layer caching
COPY pyproject.toml ./pyproject.toml


# Install the package in development mode
RUN uv sync

# Preload RAG models during Docker build to cache them
# This significantly speeds up server startup
RUN uv run python src/scripts/preload_rag_models.py

# Expose port
EXPOSE 8001

# Start the FastAPI application with uvicorn using uv run
# Note: LOG_LEVEL environment variable can be set at runtime (default: info)
CMD ["sh", "-c", "uv run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload --log-level ${LOG_LEVEL:-info}"]