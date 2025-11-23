"""
Silero VAD Service implementation using ONNX Runtime.
Inspired by LiveKit Agents' Silero plugin but tailored for this custom pipeline.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple
import asyncio

import numpy as np
import onnxruntime

logger = logging.getLogger(__name__)

class SileroVADService:
    """
    Silero VAD Service for real-time voice activity detection.
    
    Uses the Silero VAD ONNX model to detect speech in audio streams.
    Handles buffering and chunking required by the model.
    """
    
    def __init__(
        self, 
        model_path: Optional[str] = None, 
        threshold: float = 0.5, 
        sample_rate: int = 16000,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100
    ):
        """
        Initialize Silero VAD Service.
        
        Args:
            model_path: Path to the .onnx model file. If None, uses default path.
            threshold: Probability threshold for speech detection (0.0 - 1.0).
            sample_rate: Audio sample rate (must be 8000 or 16000 for Silero).
            min_speech_duration_ms: Minimum duration of speech to trigger start.
            min_silence_duration_ms: Minimum duration of silence to trigger end.
        """
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        
        if sample_rate not in [8000, 16000]:
            raise ValueError("Silero VAD only supports 8000 or 16000 Hz sample rates")
            
        # Load model
        if not model_path:
            # Default to a local path or download if needed
            # For now, we assume the model is placed in a specific directory
            current_dir = Path(__file__).parent
            model_path = str(current_dir / "silero_vad.onnx")
            
        if not os.path.exists(model_path):
            # Fallback: try to download or error out
            # In a real deployment, this should be baked into the image
            logger.warning(f"Silero model not found at {model_path}. Attempting to download...")
            self._download_model(model_path)
            
        try:
            opts = onnxruntime.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            opts.log_severity_level = 3
            
            self.session = onnxruntime.InferenceSession(
                model_path, 
                providers=['CPUExecutionProvider'], 
                sess_options=opts
            )
            logger.info(f"Silero VAD model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise

        # Model state
        self._reset_states()
        
        # Buffering
        # Silero expects specific window sizes. For 16k: 512, 1024, 1536 samples.
        # We'll use 512 samples (32ms) as the standard chunk size for inference.
        self.window_size_samples = 512 if sample_rate == 16000 else 256
        self.buffer = np.array([], dtype=np.float32)
        
        # VAD Logic State
        self.triggered = False
        self.temp_end = 0
        self.current_speech_start = 0
        self._current_probability = 0.0
        
    @property
    def current_probability(self) -> float:
        """Get the current speech probability."""
        return self._current_probability
        
    def _reset_states(self):
        """Reset internal model states (V5 uses a single state tensor)."""
        # V5 state shape: (2, 1, 128)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        
    def _download_model(self, target_path: str):
        """Download Silero VAD model (v4)."""
        import urllib.request
        import shutil
        
        urls = [
            "https://huggingface.co/onnx-community/silero-vad/resolve/main/model.onnx",
            "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
            "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
        ]
        
        for url in urls:
            try:
                logger.info(f"Attempting to download Silero VAD model from {url}...")
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
                logger.info("Download complete.")
                return
            except Exception as e:
                logger.warning(f"Failed to download from {url}: {e}")
        
        raise RuntimeError("Could not download Silero VAD model from any source")

    def process_audio_chunk(self, audio_bytes: bytes) -> List[dict]:
        """
        Process a raw PCM audio chunk and return VAD events.
        
        Args:
            audio_bytes: Raw PCM audio data (16-bit integer).
            
        Returns:
            List of VAD events (e.g. {'type': 'speech_start', ...})
        """
        # Convert bytes to float32 numpy array
        # Assumes 16-bit PCM input
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Add to buffer
        self.buffer = np.concatenate((self.buffer, audio_float32))
        
        events = []
        
        # Process in chunks of window_size_samples
        while len(self.buffer) >= self.window_size_samples:
            chunk = self.buffer[:self.window_size_samples]
            self.buffer = self.buffer[self.window_size_samples:]
            
            # Prepare input
            x = chunk[np.newaxis, :] # Add batch dimension: (1, window_size)
            
            # Run inference (V5)
            ort_inputs = {
                'input': x,
                'state': self._state,
                'sr': np.array([self.sample_rate], dtype=np.int64)
            }
            
            out, self._state = self.session.run(None, ort_inputs)
            probability = out[0][0]
            self._current_probability = float(probability)
            
            # Apply VAD logic (hysteresis)
            event = self._update_state(probability)
            if event:
                events.append(event)
                
        return events

    def _update_state(self, probability: float) -> Optional[dict]:
        """
        Update VAD state based on probability and return events.
        Simple hysteresis logic.
        """
        # This is a simplified logic. A full implementation would track 
        # min_speech_duration and min_silence_duration more robustly.
        # For now, we return the raw probability and a simple threshold trigger.
        
        is_speech = probability >= self.threshold
        
        if is_speech and not self.triggered:
            self.triggered = True
            return {
                "type": "speech_start",
                "probability": float(probability),
                "timestamp": 0 # TODO: Track timestamp
            }
            
        if not is_speech and self.triggered:
            self.triggered = False
            return {
                "type": "speech_end",
                "probability": float(probability),
                "timestamp": 0
            }
            
        return None

    def reset(self):
        """Reset VAD state."""
        self._reset_states()
        self.buffer = np.array([], dtype=np.float32)
        self.triggered = False
