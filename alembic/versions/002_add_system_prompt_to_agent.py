"""Add system_prompt column to agents table

Revision ID: 002
Revises: 001
Create Date: 2025-12-01 16:18:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # Add system_prompt column to agents table
    op.add_column("agents", sa.Column("system_prompt", sa.Text(), nullable=True))

    # Update existing agents with default system prompt (optional)
    # We'll keep it null for now, can be populated later via migration script if needed


def downgrade():
    # Remove system_prompt column
    op.drop_column("agents", "system_prompt")
