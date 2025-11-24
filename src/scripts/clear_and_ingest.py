#!/usr/bin/env python3
"""Script to clear the Qdrant collection and ingest a document."""

import argparse
import os
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

def clear_qdrant_collection(host="qdrant", port=6333, collection="voicebot_knowledge"):
    """Clear the specified Qdrant collection."""
    client = QdrantClient(host=host, port=port)

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

def ingest_document(file_path, namespace="bayview-banking", host="qdrant", port=6333):
    """Ingest a document directly into Qdrant."""
    # Add scripts directory to Python path
    sys.path.insert(0, '/app/scripts')
    
    # Import the ingest_documents module
    from ingest_documents import _build_payload

    # Build the payload using the existing function
    path = Path(file_path)
    payload = _build_payload([path], namespace=namespace, target_words=180, max_words=240)

    print(f"Prepared {len(payload['documents'])} chunks for ingestion")
    
    # Get Qdrant client
    client = QdrantClient(host=host, port=port)
    
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
        "--qdrant-host",
        default="qdrant",
        help="Qdrant host (default: %(default)s)",
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant port (default: %(default)s)",
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
        host=args.qdrant_host,
        port=args.qdrant_port,
        collection=args.collection,
    )

    # Ingest the document
    print(f"Ingesting document: {args.file}")
    ingest_document(
        file_path=args.file,
        namespace=args.namespace,
        host=args.qdrant_host,
        port=args.qdrant_port,
    )

    print("Document ingestion completed successfully!")

if __name__ == "__main__":
    main()