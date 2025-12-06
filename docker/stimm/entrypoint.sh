#!/bin/bash
set -e

# Wait for PostgreSQL to be ready (max 30 seconds)
echo "Waiting for PostgreSQL to be ready..."
timeout=30
while ! nc -z postgres 5432; do
  sleep 1
  timeout=$((timeout - 1))
  if [ $timeout -eq 0 ]; then
    echo "PostgreSQL is not available after 30 seconds, exiting."
    exit 1
  fi
done

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting stimm API server..."
exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload --log-level ${LOG_LEVEL:-info}