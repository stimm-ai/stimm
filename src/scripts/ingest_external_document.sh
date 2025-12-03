#!/bin/bash
# DEPRECATED: Script to ingest an external markdown document into voicebot-app
# This script is deprecated in favor of the new RAG admin management API.
# Use the upload endpoints via /rag-configs/{rag_config_id}/documents/upload instead.

DOCUMENT_PATH="$1"
DOCUMENT_NAME=$(basename "$DOCUMENT_PATH")

if [ -z "$DOCUMENT_PATH" ]; then
    echo "Usage: $0 <path_to_markdown_file>"
    exit 1
fi

if [ ! -f "$DOCUMENT_PATH" ]; then
    echo "Error: File '$DOCUMENT_PATH' not found"
    exit 1
fi

echo "Creating knowledge_base directory in container..."
docker exec voicebot-app mkdir -p /app/knowledge_base

echo "Copying $DOCUMENT_PATH to voicebot-app container..."
docker cp "$DOCUMENT_PATH" voicebot-app:/app/knowledge_base/

echo "Running document ingestion..."
docker exec voicebot-app python /app/scripts/clear_and_ingest.py "/app/knowledge_base/$DOCUMENT_NAME"

echo "Cleaning up temporary file..."
docker exec voicebot-app rm "/app/knowledge_base/$DOCUMENT_NAME"

echo "Document ingestion completed!"