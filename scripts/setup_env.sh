#!/bin/bash
# Setup environment files by copying .env.example files to .env

echo "Setting up environment files..."

# Copy root .env.example to .env
cp .env.example .env || { echo "Failed to copy root .env.example"; exit 1; }

# Copy docker/stimm .env.example to .env
cp docker/stimm/.env.example docker/stimm/.env || { echo "Failed to copy docker/stimm/.env.example"; exit 1; }

# Copy src/front .env.example to .env
cp src/front/.env.example src/front/.env || { echo "Failed to copy src/front/.env.example"; exit 1; }

echo "Environment files setup complete."
echo "Please review and update the .env files with your specific configuration."