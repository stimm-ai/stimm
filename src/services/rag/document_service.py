"""
Document Service

This module provides CRUD operations for document management in RAG configurations.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.models import Document, RagConfig
from services.agents_admin.exceptions import AgentNotFoundError

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for managing documents in RAG configurations."""

    def __init__(self, db: Session):
        self.db = db

    def create_document(
        self,
        rag_config_id: str,
        filename: str,
        file_type: str,
        file_size_bytes: Optional[int],
        chunk_count: int,
        chunk_ids: List[str],
        namespace: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Document:
        """
        Create a new document record.

        Args:
            rag_config_id: ID of the RAG configuration
            filename: Name of the file
            file_type: Type of file (pdf, docx, markdown, text)
            file_size_bytes: Size of file in bytes
            chunk_count: Number of chunks created
            chunk_ids: List of Qdrant point IDs
            namespace: Optional namespace
            metadata: Optional additional metadata

        Returns:
            Created document

        Raises:
            AgentNotFoundError: If RAG config not found
        """
        # Verify RAG config exists
        rag_config = self.db.query(RagConfig).filter(RagConfig.id == uuid.UUID(rag_config_id)).first()
        if not rag_config:
            raise AgentNotFoundError(f"RAG configuration {rag_config_id} not found")

        document = Document(
            id=uuid.uuid4(),
            rag_config_id=uuid.UUID(rag_config_id),
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            chunk_count=chunk_count,
            chunk_ids=chunk_ids,
            namespace=namespace,
            doc_metadata=metadata or {},  # Use doc_metadata field
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_documents(
        self,
        rag_config_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Document], int]:
        """
        List documents for a RAG configuration.

        Args:
            rag_config_id: ID of the RAG configuration
            skip: Number of documents to skip
            limit: Maximum number of documents to return

        Returns:
            Tuple of (documents, total_count)
        """
        query = self.db.query(Document).filter(Document.rag_config_id == uuid.UUID(rag_config_id))

        total = query.count()
        documents = query.order_by(desc(Document.created_at)).offset(skip).limit(limit).all()

        return documents, total

    def get_document(self, document_id: str) -> Optional[Document]:
        """
        Get a document by ID.

        Args:
            document_id: Document ID

        Returns:
            Document or None if not found
        """
        return self.db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()

    def delete_document(self, document_id: str) -> Document:
        """
        Delete a document.

        Args:
            document_id: Document ID

        Returns:
            Deleted document

        Raises:
            AgentNotFoundError: If document not found
        """
        document = self.get_document(document_id)
        if not document:
            raise AgentNotFoundError(f"Document {document_id} not found")

        self.db.delete(document)
        self.db.commit()
        return document

    def delete_all_documents(self, rag_config_id: str) -> int:
        """
        Delete all documents for a RAG configuration.

        Args:
            rag_config_id: ID of the RAG configuration

        Returns:
            Number of documents deleted
        """
        count = self.db.query(Document).filter(Document.rag_config_id == uuid.UUID(rag_config_id)).delete()
        self.db.commit()
        return count

    def get_statistics(self, rag_config_id: str) -> dict:
        """
        Get statistics for documents in a RAG configuration.

        Args:
            rag_config_id: ID of the RAG configuration

        Returns:
            Dictionary with statistics
        """
        documents = self.db.query(Document).filter(Document.rag_config_id == uuid.UUID(rag_config_id)).all()

        total_documents = len(documents)
        total_chunks = sum(doc.chunk_count for doc in documents)
        total_size = sum(doc.file_size_bytes or 0 for doc in documents)

        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
        }
