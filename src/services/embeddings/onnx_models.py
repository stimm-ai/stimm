"""
ONNX-based embedding models to replace sentence_transformers without PyTorch dependency.

This module provides lightweight embedding and reranking models using ONNX Runtime
instead of PyTorch, significantly reducing dependency size and complexity.
"""

import logging
from typing import List, Optional, Union

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)


class ONNXSentenceTransformer:
    """
    Drop-in replacement for sentence_transformers.SentenceTransformer using ONNX Runtime.

    This class provides a compatible interface with SentenceTransformer but uses ONNX
    for inference, eliminating the PyTorch dependency.
    """

    def __init__(self, model_name: str, cache_folder: Optional[str] = None):
        """
        Initialize the ONNX-based sentence transformer.

        Args:
            model_name: HuggingFace model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')
            cache_folder: Optional cache directory for model files
        """
        self.model_name = model_name
        self._embedding_dimension = None

        logger.info(f"Loading ONNX embedding model: {model_name}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_folder)

        # Try to load pre-converted ONNX model from Optimum repository
        # Many popular models are pre-converted and available at optimum/{model_name}
        onnx_model_name = f"optimum/{model_name.split('/')[-1]}"

        try:
            from huggingface_hub import hf_hub_download

            # Download ONNX model file
            model_path = hf_hub_download(
                repo_id=onnx_model_name,
                filename="model.onnx",
                cache_dir=cache_folder,
            )

            # Create ONNX Runtime session
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=["CPUExecutionProvider"])
            logger.info(f"Successfully loaded pre-converted ONNX model: {onnx_model_name}")

        except Exception as e:
            logger.error(f"Failed to load pre-converted ONNX model from {onnx_model_name}: {e}")
            logger.error("Please convert your model to ONNX format first.")
            logger.error(f"Try using: from optimum.exporters.onnx import main_export; main_export('{model_name}')")
            raise RuntimeError(f"ONNX model not found for {model_name}. Please use a pre-converted model from https://huggingface.co/optimum or convert your model to ONNX format manually.")

    def encode(
        self,
        sentences: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        """
        Encode sentences into embeddings.

        Args:
            sentences: Single sentence or list of sentences to encode
            batch_size: Batch size for encoding (not used in current implementation)
            show_progress_bar: Whether to show progress bar (ignored)
            convert_to_numpy: Whether to return numpy array (always True)
            normalize_embeddings: Whether to L2-normalize embeddings

        Returns:
            numpy array of embeddings
        """
        # Handle single string input
        if isinstance(sentences, str):
            sentences = [sentences]

        # Tokenize input
        inputs = self.tokenizer(
            sentences,
            padding=True,
            truncation=True,
            return_tensors="np",  # Return numpy arrays
            max_length=512,
        )

        # Run ONNX inference
        try:
            # Prepare inputs for ONNX Runtime
            ort_inputs = {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64),
            }

            # Add token_type_ids if present (BERT-style models)
            if "token_type_ids" in inputs:
                ort_inputs["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

            # Run inference
            ort_outputs = self.session.run(None, ort_inputs)

            # The output is typically the last hidden state
            # Shape: (batch_size, sequence_length, hidden_size)
            last_hidden_state = ort_outputs[0]
            attention_mask = inputs["attention_mask"]

            # Mean pooling - average over all tokens, weighted by attention mask
            input_mask_expanded = np.expand_dims(attention_mask, axis=-1)
            input_mask_expanded = np.broadcast_to(input_mask_expanded, last_hidden_state.shape).astype(np.float32)

            # Sum embeddings and divide by number of non-padding tokens
            embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1) / np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)

            # Normalize if requested
            if normalize_embeddings:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / np.clip(norms, a_min=1e-9, a_max=None)

            return embeddings

        except Exception as e:
            logger.error(f"Error during encoding: {e}")
            raise

    def get_sentence_embedding_dimension(self) -> int:
        """
        Get the dimension of the sentence embeddings.

        Returns:
            Embedding dimension size
        """
        if self._embedding_dimension is None:
            # Encode a dummy sentence to get dimension
            dummy_embedding = self.encode(["test"], show_progress_bar=False)
            self._embedding_dimension = dummy_embedding.shape[1]
        return self._embedding_dimension


class ONNXCrossEncoder:
    """
    Drop-in replacement for sentence_transformers.CrossEncoder using ONNX Runtime.

    This class provides a compatible interface with CrossEncoder but uses ONNX
    for inference, eliminating the PyTorch dependency.
    """

    def __init__(self, model_name: str, max_length: int = 512):
        """
        Initialize the ONNX-based cross encoder.

        Args:
            model_name: HuggingFace model name for cross-encoder
            max_length: Maximum sequence length
        """
        self.model_name = model_name
        self.max_length = max_length

        logger.info(f"Loading ONNX cross-encoder model: {model_name}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Try to load pre-converted ONNX model
        onnx_model_name = f"optimum/{model_name.split('/')[-1]}"

        try:
            from huggingface_hub import hf_hub_download

            # Download ONNX model file
            model_path = hf_hub_download(
                repo_id=onnx_model_name,
                filename="model.onnx",
            )

            # Create ONNX Runtime session
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=["CPUExecutionProvider"])
            logger.info(f"Successfully loaded ONNX cross-encoder: {onnx_model_name}")

        except Exception as e:
            logger.error(f"Failed to load ONNX cross-encoder {model_name}: {e}")
            raise RuntimeError(f"ONNX cross-encoder not found for {model_name}. Please use a pre-converted model from https://huggingface.co/optimum")

    def predict(
        self,
        sentences: List[tuple],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """
        Predict relevance scores for sentence pairs.

        Args:
            sentences: List of (query, document) tuples
            batch_size: Batch size for prediction (not used in current implementation)
            show_progress_bar: Whether to show progress bar (ignored)

        Returns:
            numpy array of relevance scores
        """
        if not sentences:
            return np.array([])

        # Prepare inputs for the model
        features = self.tokenizer(
            sentences,
            padding=True,
            truncation=True,
            return_tensors="np",  # Return numpy arrays
            max_length=self.max_length,
        )

        # Run ONNX inference
        try:
            # Prepare inputs for ONNX Runtime
            ort_inputs = {
                "input_ids": features["input_ids"].astype(np.int64),
                "attention_mask": features["attention_mask"].astype(np.int64),
            }

            # Add token_type_ids if present
            if "token_type_ids" in features:
                ort_inputs["token_type_ids"] = features["token_type_ids"].astype(np.int64)

            # Run inference
            ort_outputs = self.session.run(None, ort_inputs)

            # The output is the logits for classification
            logits = ort_outputs[0]

            # For binary cross-encoders, typically return the positive class score
            # If single output, use that; if two outputs, use the second one
            if logits.shape[1] == 1:
                scores = logits[:, 0]
            else:
                scores = logits[:, 1]

            return scores

        except Exception as e:
            logger.error(f"Error during cross-encoder prediction: {e}")
            raise


# Compatibility exports - these can be imported just like sentence_transformers
SentenceTransformer = ONNXSentenceTransformer
CrossEncoder = ONNXCrossEncoder
