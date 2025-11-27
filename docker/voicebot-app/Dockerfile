# Use Python 3.10-slim for optimal size and performance
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set Python path
ENV PYTHONPATH=/app

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

# Copy pyproject.toml first for better Docker layer caching
# Build context is at ../../src, so we copy from current dir
COPY pyproject.toml ./pyproject.toml
COPY requirements.txt ./requirements.txt

# Install dependencies using uv with requirements.txt for backward compatibility
RUN uv pip install --system -r requirements.txt

# Copy source code
COPY . ./

# Install environment configuration module
RUN uv pip install --system -e .

# Copy scripts and other files needed for initialization
COPY scripts/ ./scripts/

# Preload RAG models during Docker build to cache them
# This significantly speeds up server startup
RUN python scripts/preload_rag_models.py

# Expose port
EXPOSE 8001

# Start the FastAPI application with uvicorn
# Note: LOG_LEVEL environment variable can be set at runtime (default: info)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8001 --reload --log-level ${LOG_LEVEL:-info}"]