#!/bin/bash
# Setup environment files by copying .env.example files to .env
# Also sets up Python path via .pth file in virtual environment.

echo "Setting up environment files..."

# Copy root .env.example to .env
cp .env.example .env || { echo "Failed to copy root .env.example"; exit 1; }

# Copy docker/stimm .env.example to .env
cp docker/stimm/.env.example docker/stimm/.env || { echo "Failed to copy docker/stimm/.env.example"; exit 1; }

# Copy src/front .env.example to .env
cp src/front/.env.example src/front/.env || { echo "Failed to copy src/front/.env.example"; exit 1; }

echo "Environment files setup complete."
echo "Please review and update the .env files with your specific configuration."

# Optionally set up Python path
echo ""
echo "Setting up Python path..."
if command -v uv &> /dev/null && [ -d ".venv" ]; then
    if [ -f "scripts/setup_pythonpath.py" ]; then
        uv run python scripts/setup_pythonpath.py
    else
        echo "Warning: scripts/setup_pythonpath.py not found. Skipping Python path setup."
    fi
elif command -v python3 &> /dev/null; then
    if [ -f "scripts/setup_pythonpath.py" ]; then
        echo "Warning: Using system python3; .pth file may be installed globally."
        python3 scripts/setup_pythonpath.py
    else
        echo "Warning: scripts/setup_pythonpath.py not found. Skipping Python path setup."
    fi
else
    echo "Warning: python3 not found. Skipping Python path setup."
fi