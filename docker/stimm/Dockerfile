# Build stage
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (most reliable method)
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (without dev dependencies)
# We create a virtual environment in /app/.venv
# Note: we don't install the project itself yet to avoid frequent cache invalidation
RUN uv sync --no-dev --no-install-project

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Set PYTHONPATH to ensure the application can find the src/ directory
ENV PYTHONPATH=/app/src
# Add venv bin to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libportaudio2 \
    pulseaudio-utils \
    libpulse0 \
    ffmpeg \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code and configuration
COPY src/ src/
COPY pyproject.toml ./pyproject.toml
COPY alembic.ini ./alembic.ini
COPY alembic/ alembic/
COPY docker/stimm/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8001

# Use entrypoint script
CMD ["/entrypoint.sh"]