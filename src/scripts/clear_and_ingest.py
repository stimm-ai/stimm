#!/usr/bin/env python3
"""DEPRECATED: Script to clear the Qdrant collection and ingest a document.

This script is deprecated in favor of the new RAG admin management API.
Use the upload endpoints via /rag-configs/{rag_config_id}/documents/upload instead.
"""

import argparse
import os
import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# Import environment configuration for dual-mode support
from environment_config import config

def get_qdrant_connection():
    """Get environment-aware Qdrant connection"""
    qdrant_url = config.qdrant_url
    
    if "://" in qdrant_url:
        protocol_and_host = qdrant_url.split("://")[1]
        if ":" in protocol_and_host:
            host, port_part = protocol_and_host.split(":")
            port = int(port_part.split("/")[0])
        else:
            host = protocol_and_host.split("/")[0]
            port = 6333
    else:
        # Fallback for invalid URL
        host = "localhost"
        port = 6333
        
    return QdrantClient(host=host, port=port), host, port

def clear_qdrant_collection(collection="voicebot_knowledge"):
    """Clear the specified Qdrant collection."""
    client, host, port = get_qdrant_connection()
    print(f"Connecting to Qdrant at {host}:{port}")

    # Check if collection exists
    collections = client.get_collections()
    collection_names = {col.name for col in collections.collections}

    if collection not in collection_names:
        print(f"Collection '{collection}' does not exist. Creating it...")
        # Create the collection with default vector size
        client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=768, distance=qmodels.Distance.COSINE),
        )
    else:
        # Delete all points in the collection
        print(f"Clearing collection '{collection}'...")
        client.delete(
            collection_name=collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(
                        key="id",
                        match=qmodels.MatchAny(any=[])
                    )]
                )
            )
        )

    print(f"Collection '{collection}' is now empty.")
    return client

def ingest_document(file_path, namespace="bayview-banking"):
    """Ingest a document directly into Qdrant."""
    # Add scripts directory to Python path
    sys.path.insert(0, str(Path(__file__).parent))
    
    # Import the ingest_documents module
    from ingest_documents import _build_payload

    # Build the payload using the existing function
    path = Path(file_path)
    payload = _build_payload([path], namespace=namespace, target_words=180, max_words=240)

    print(f"Prepared {len(payload['documents'])} chunks for ingestion")
    
    # Get Qdrant client
    client, host, port = get_qdrant_connection()
    print(f"Connecting to Qdrant at {host}:{port}")
    
    # Generate embeddings for the documents using the same model as voicebot-app
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
    
    # Ingest chunks directly into Qdrant
    import uuid
    
    points = []
    for chunk in payload['documents']:
        # Generate embedding for the text
        embedding = embedder.encode(chunk['text']).tolist()
        
        point_id = str(uuid.uuid4())
        point = qmodels.PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "text": chunk['text'],
                "namespace": chunk['namespace'],
                "source": chunk['metadata']['source'],
                "chunk_index": chunk['metadata']['chunk_index'],
                "total_chunks": chunk['metadata']['chunks_total']
            }
        )
        points.append(point)
    
    # Upsert the points
    client.upsert(
        collection_name="voicebot_knowledge",
        points=points
    )
    
    print(f"Successfully ingested {len(points)} chunks into Qdrant")

def main():
    """Main function to clear Qdrant and ingest a document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the markdown file to ingest",
    )
    parser.add_argument(
        "--collection",
        default="voicebot_knowledge",
        help="Qdrant collection name (default: %(default)s)",
    )
    parser.add_argument(
        "--namespace",
        default="bayview-banking",
        help="Namespace for the documents (default: %(default)s)",
    )

    args = parser.parse_args()

    # Clear the Qdrant collection
    client = clear_qdrant_collection(
        collection=args.collection,
    )

    # Ingest the document
    print(f"Ingesting document: {args.file}")
    ingest_document(
        file_path=args.file,
        namespace=args.namespace,
    )

    print("Document ingestion completed successfully!")

if __name__ == "__main__":
    main()