"""
RAG Configuration Management API Routes

This module provides FastAPI routes for managing RAG configurations, including:
- CRUD operations for RAG configs
- Default RAG config management
- Provider configuration management
- Document management (upload, list, delete)
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from .rag_config_service import RagConfigService
from .document_service import DocumentService
from .document_processor import process_uploaded_file, DocumentType
from .retrieval_engine import RetrievalEngine
from .config_models import (
    RagConfigCreate,
    RagConfigUpdate,
    RagConfigResponse,
    RagConfigListResponse,
    ProviderConfig,
)
from services.agents_admin.exceptions import (
    AgentNotFoundError,
    AgentAlreadyExistsError,
    AgentValidationError,
)
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag-configs", tags=["rag-configs"])


@router.get("/", response_model=List[RagConfigResponse])
async def list_rag_configs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all RAG configurations with pagination"""
    rag_config_service = RagConfigService(db)
    configs_result = rag_config_service.list_rag_configs(skip=skip, limit=limit)
    return configs_result.configs


@router.get("/{rag_config_id}", response_model=RagConfigResponse)
async def get_rag_config(
    rag_config_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific RAG configuration by ID"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config = rag_config_service.get_rag_config(rag_config_id)
        return rag_config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RAG configuration with ID {rag_config_id} not found"
        )


@router.post("/", response_model=RagConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_rag_config(
    rag_config_data: RagConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new RAG configuration"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config = rag_config_service.create_rag_config(rag_config_data)
        # Ensure collection exists for vector database providers
        if rag_config.provider == 'qdrant.internal':
            try:
                config = rag_config.provider_config or {}
                engine = RetrievalEngine(
                    collection_name=config.get('collection_name'),
                    embed_model_name=config.get('embedding_model'),
                )
                await engine.ensure_collection()
                logger.info(f"Ensured collection exists for RAG config {rag_config.id}")
            except Exception as e:
                # Log but don't fail creation, as collection can be created later
                logger.warning(f"Failed to ensure collection for new RAG config {rag_config.id}: {e}")
        return rag_config
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "errors": [str(e)]}
        )
    except AgentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "errors": [str(e)]}
        )
    except Exception as e:
        logger.error(f"Failed to create RAG configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create RAG configuration", "errors": [str(e)]}
        )


@router.put("/{rag_config_id}", response_model=RagConfigResponse)
async def update_rag_config(
    rag_config_id: str,
    rag_config_data: RagConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing RAG configuration"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config = rag_config_service.update_rag_config(rag_config_id, rag_config_data)
        return rag_config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RAG configuration with ID {rag_config_id} not found"
        )
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AgentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update RAG configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update RAG configuration"
        )


@router.delete("/{rag_config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_config(
    rag_config_id: str,
    db: Session = Depends(get_db)
):
    """Delete a RAG configuration"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config_service.delete_rag_config(rag_config_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RAG configuration with ID {rag_config_id} not found"
        )
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete RAG configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete RAG configuration"
        )


@router.get("/default/current", response_model=RagConfigResponse)
async def get_default_rag_config(
    db: Session = Depends(get_db)
):
    """Get the current default RAG configuration"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config = rag_config_service.get_default_rag_config()
        return rag_config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default RAG configuration found"
        )


@router.put("/{rag_config_id}/set-default", response_model=RagConfigResponse)
async def set_default_rag_config(
    rag_config_id: str,
    db: Session = Depends(get_db)
):
    """Set a RAG configuration as the default"""
    rag_config_service = RagConfigService(db)
    try:
        rag_config = rag_config_service.set_default_rag_config(rag_config_id)
        return rag_config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RAG configuration with ID {rag_config_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to set default RAG configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default RAG configuration"
        )


@router.get("/providers/available", response_model=Dict[str, Any])
async def get_available_rag_providers():
    """Get available RAG providers with their expected properties"""
    try:
        from services.agents_admin.provider_registry import get_provider_registry

        registry = get_provider_registry()
        providers_data = registry.get_available_providers()

        # Extract only RAG providers
        rag_providers = providers_data.get("rag", {})
        return rag_providers
    except Exception as e:
        logger.error(f"Failed to load available RAG providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load available RAG providers"
        )


@router.get("/providers/{provider_name}/fields", response_model=Dict[str, Any])
async def get_rag_provider_fields(provider_name: str):
    """Get field definitions for a specific RAG provider"""
    try:
        from services.agents_admin.provider_registry import get_provider_registry

        registry = get_provider_registry()
        field_definitions = registry.get_provider_field_definitions("rag", provider_name)

        # Return empty dict if provider has no configurable fields
        return field_definitions or {}
    except Exception as e:
        logger.error(f"Failed to get provider fields for rag.{provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get field definitions for provider rag.{provider_name}"
        )


# ============================================================================
# Document Management Endpoints
# ============================================================================

@router.post("/{rag_config_id}/documents/upload")
async def upload_documents(
    rag_config_id: str,
    files: List[UploadFile] = File(...),
    namespace: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload and ingest documents into a RAG configuration.
    
    Supports PDF, DOCX, Markdown, and text files.
    """
    doc_service = DocumentService(db)
    rag_config_service = RagConfigService(db)
    
    try:
        # Verify RAG config exists
        rag_config = rag_config_service.get_rag_config(rag_config_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RAG configuration {rag_config_id} not found"
        )
    
    # Create retrieval engine for this RAG config
    try:
        config = rag_config.provider_config or {}
        logger.info(f"Using provider config: {config}")
        
        engine = RetrievalEngine(
            collection_name=config.get("collection_name"),
            embed_model_name=config.get("embedding_model"),
            enable_reranker=config.get("enable_reranker", False),
        )
    except Exception as e:
        logger.error(f"Failed to initialize RetrievalEngine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize RetrievalEngine: {str(e)}"
        )
    
    # Ensure the collection exists before uploading
    try:
        await engine.ensure_collection()
    except Exception as e:
        logger.error(f"Failed to ensure collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ensure collection: {str(e)}"
        )
    
    uploaded_docs = []
    errors = []
    
    for file in files:
        try:
            # Read file content
            content = await file.read()
            
            # Process and chunk the document
            chunks, file_type = process_uploaded_file(
                filename=file.filename,
                content=content,
                namespace=namespace,
            )
            
            if not chunks:
                errors.append({"filename": file.filename, "error": "No chunks generated"})
                continue
            
            # Prepare documents for ingestion
            documents = [chunk.to_payload() for chunk in chunks]
            
            # Embed and ingest into vector database
            texts = [doc["text"] for doc in documents]
            embeddings = engine.embedder.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            
            # Create Qdrant points
            from qdrant_client.http import models as qmodels
            points = []
            for doc, embedding in zip(documents, embeddings):
                # Build payload with text and flattened metadata
                payload = {}
                payload["text"] = doc["text"]
                if "namespace" in doc:
                    payload["namespace"] = doc["namespace"]
                # Merge metadata into payload (flatten)
                metadata = doc.get("metadata", {})
                for key, value in metadata.items():
                    payload[key] = value
                points.append(
                    qmodels.PointStruct(
                        id=doc["id"],
                        vector=embedding.tolist(),
                        payload=payload,
                    )
                )
            
            # Upsert to Qdrant
            collection_name = config.get("collection_name", "stimm_knowledge")
            engine.client.upsert(collection_name=collection_name, points=points)
            
            # Create document record
            chunk_ids = [doc["id"] for doc in documents]
            document = doc_service.create_document(
                rag_config_id=rag_config_id,
                filename=file.filename,
                file_type=file_type.value,
                file_size_bytes=len(content),
                chunk_count=len(chunks),
                chunk_ids=chunk_ids,
                namespace=namespace,
            )
            
            uploaded_docs.append(document.to_dict())
            logger.info(f"Uploaded {file.filename}: {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "uploaded": uploaded_docs,
        "errors": errors,
        "total_uploaded": len(uploaded_docs),
        "total_errors": len(errors),
    }


@router.get("/{rag_config_id}/documents")
async def list_documents(
    rag_config_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all documents for a RAG configuration."""
    doc_service = DocumentService(db)
    
    try:
        documents, total = doc_service.list_documents(
            rag_config_id=rag_config_id,
            skip=skip,
            limit=limit,
        )
        
        return {
            "documents": [doc.to_dict() for doc in documents],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.delete("/{rag_config_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    rag_config_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    """Delete a specific document and its chunks from the vector database."""
    doc_service = DocumentService(db)
    rag_config_service = RagConfigService(db)
    
    try:
        # Get the document
        document = doc_service.get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Verify it belongs to this RAG config
        if str(document.rag_config_id) != rag_config_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document does not belong to this RAG configuration"
            )
        
        # Get RAG config
        rag_config = rag_config_service.get_rag_config(rag_config_id)
        config = rag_config.provider_config or {}
        
        # Create retrieval engine
        engine = RetrievalEngine(
            collection_name=config.get("collection_name"),
        )
        
        # Delete chunks from Qdrant
        collection_name = config.get("collection_name", "stimm_knowledge")
        engine.client.delete(
            collection_name=collection_name,
            points_selector=document.chunk_ids,
        )
        
        # Delete document record
        doc_service.delete_document(document_id)
        logger.info(f"Deleted document {document_id} and its {len(document.chunk_ids)} chunks")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.delete("/{rag_config_id}/documents", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_documents(
    rag_config_id: str,
    db: Session = Depends(get_db)
):
    """Delete all documents for a RAG configuration."""
    doc_service = DocumentService(db)
    rag_config_service = RagConfigService(db)
    
    try:
        # Get RAG config
        rag_config = rag_config_service.get_rag_config(rag_config_id)
        config = rag_config.provider_config or {}
        
        # Get all documents
        documents, _ = doc_service.list_documents(rag_config_id, skip=0, limit=10000)
        
        if documents:
            # Create retrieval engine
            engine = RetrievalEngine(
                collection_name=config.get("collection_name"),
            )
            
            # Collect all chunk IDs
            all_chunk_ids = []
            for doc in documents:
                all_chunk_ids.extend(doc.chunk_ids)
            
            # Delete from Qdrant
            collection_name = config.get("collection_name", "stimm_knowledge")
            engine.client.delete(
                collection_name=collection_name,
                points_selector=all_chunk_ids,
            )
        
        # Delete all document records
        count = doc_service.delete_all_documents(rag_config_id)
        logger.info(f"Deleted {count} documents from RAG config {rag_config_id}")
        
    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete all documents: {str(e)}"
        )


@router.get("/{rag_config_id}/documents/statistics")
async def get_documents_statistics(
    rag_config_id: str,
    db: Session = Depends(get_db)
):
    """Get statistics about documents in a RAG configuration."""
    doc_service = DocumentService(db)
    
    try:
        stats = doc_service.get_statistics(rag_config_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get document statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.post("/preload/{agent_id}")
async def preload_rag_for_agent(agent_id: str):
    """
    Preload RAG state for a specific agent.
    
    This allows the frontend to trigger RAG preloading when an agent is selected,
    providing immediate user feedback and faster connection times.
    """
    try:
        from services.rag.rag_preloader import rag_preloader
        
        logger.info(f"Preloading RAG for agent {agent_id}")
        await rag_preloader.get_rag_state_for_agent(agent_id=agent_id)
        
        return {"status": "success", "message": f"RAG preloaded for agent {agent_id}"}
    except Exception as e:
        logger.error(f"Failed to preload RAG for agent {agent_id}: {e}")
        return {"status": "error", "error": str(e)}