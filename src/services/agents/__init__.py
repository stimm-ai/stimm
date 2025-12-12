"""

Stimm wrapper package for complete voice assistant integration.

This package provides a unified interface for STT, RAG/LLM, and TTS services
with real-time voice activity detection and streaming conversation capabilities.
"""

__version__ = "1.0.0"
__author__ = "Stimm Team"

from .config import StimmConfig
from .stimm_service import StimmService

__all__ = ["StimmService", "StimmConfig"]
