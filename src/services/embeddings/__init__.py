"""
Embeddings module - provides lightweight ONNX-based embedding models.

This module exports drop-in replacements for sentence_transformers models
that use ONNX Runtime instead of PyTorch, eliminating heavy dependencies.
"""

from .onnx_models import CrossEncoder, SentenceTransformer

__all__ = ["SentenceTransformer", "CrossEncoder"]
