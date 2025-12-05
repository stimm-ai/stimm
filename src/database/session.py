"""
Database session management for stimm application.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from environment_config import config

load_dotenv()

# Create engine with connection pooling (lazy loaded)
_engine = None
_session_factory = None

def _get_engine():
    """Get or create the database engine, ensuring environment config is loaded."""
    global _engine
    if _engine is None:
        # Force environment config loading to get correct database URL
        actual_db_url = config.database_url
        
        _engine = create_engine(
            actual_db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )
    return _engine

def _get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _session_factory

# Session factory
SessionLocal = _get_session_factory()

# Base class for models
Base = declarative_base()

def get_db():
    """
    Dependency function to get database session.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """
    Create all tables in the database.
    Should only be used for development/testing.
    """
    Base.metadata.create_all(bind=_get_engine())

def drop_tables():
    """
    Drop all tables in the database.
    Should only be used for development/testing.
    """
    Base.metadata.drop_all(bind=_get_engine())

def get_engine():
    """
    Get the database engine instance.
    Used by other modules that need direct access to the engine.
    """
    return _get_engine()