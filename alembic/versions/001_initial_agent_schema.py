"""Initial agent management schema

Revision ID: 001
Revises: 
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Create agents table
    op.create_table('agents',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('llm_provider', sa.String(length=50), nullable=False),
        sa.Column('tts_provider', sa.String(length=50), nullable=False),
        sa.Column('stt_provider', sa.String(length=50), nullable=False),
        sa.Column('llm_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('tts_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('stt_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('is_system_agent', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_agents_user_id', 'agents', ['user_id'])
    op.create_index('idx_agents_is_default', 'agents', ['is_default'], postgresql_where=sa.text('is_default = true'))
    op.create_index('idx_agents_is_active', 'agents', ['is_active'], postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_agents_user_default', 'agents', ['user_id'], unique=True, postgresql_where=sa.text('is_default = true'))
    
    # Create agent_sessions table
    op.create_table('agent_sessions',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('agent_id', postgresql.UUID(), nullable=False),
        sa.Column('session_type', sa.String(length=50), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_agent_sessions_user_agent', 'agent_sessions', ['user_id', 'agent_id'])
    op.create_index('idx_agent_sessions_expires', 'agent_sessions', ['expires_at'])
    
    # Insert system user
    op.execute("""
        INSERT INTO users (id, username, email)
        VALUES ('00000000-0000-0000-0000-000000000000', 'system', 'system@stimm.local')
    """)


def downgrade():
    op.drop_index('idx_agent_sessions_expires', table_name='agent_sessions')
    op.drop_index('idx_agent_sessions_user_agent', table_name='agent_sessions')
    op.drop_table('agent_sessions')
    
    op.drop_index('idx_agents_user_default', table_name='agents')
    op.drop_index('idx_agents_is_active', table_name='agents')
    op.drop_index('idx_agents_is_default', table_name='agents')
    op.drop_index('idx_agents_user_id', table_name='agents')
    op.drop_table('agents')
    
    op.drop_table('users')