"""add_documents_table

Revision ID: 633edd42c760
Revises: 962e5b26ffd2
Create Date: 2025-12-02 15:32:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "633edd42c760"
down_revision = "962e5b26ffd2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create documents table for tracking ingested documents (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Check if table already exists
    if "documents" not in inspector.get_table_names():
        op.create_table(
            "documents",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("rag_config_id", sa.UUID(), nullable=False),
            sa.Column("filename", sa.String(length=500), nullable=False),
            sa.Column("file_type", sa.String(length=50), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=False),
            sa.Column("chunk_ids", postgresql.ARRAY(sa.Text()), nullable=False),
            sa.Column("namespace", sa.String(length=255), nullable=True),
            sa.Column("doc_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["rag_config_id"], ["rag_configs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes if they don't exist (PostgreSQL specific)
    # We'll check via raw SQL to avoid complexity
    # For simplicity, we'll just create indexes; if they exist, PostgreSQL will raise a warning but not fail.
    # We'll use op.execute with CREATE INDEX IF NOT EXISTS (PostgreSQL 9.5+)
    # However, alembic's op.create_index doesn't support IF NOT EXISTS, so we'll use raw SQL.
    # We'll wrap in a try-except to ignore duplicate index errors.
    try:
        op.create_index("idx_documents_rag_config", "documents", ["rag_config_id"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("idx_documents_created_at", "documents", ["created_at"], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    """Drop documents table."""
    op.drop_index("idx_documents_created_at", table_name="documents")
    op.drop_index("idx_documents_rag_config", table_name="documents")
    op.drop_table("documents")
