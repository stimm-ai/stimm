import os
import logging
import numpy as np
import onnxruntime
import asyncio
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SileroVADService:
    """
    Silero VAD Service using ONNX Runtime.
    """
    def __init__(self, model_path: str = None, threshold: float = 0.3, sampling_rate: int = 16000):
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.min_speech_duration_ms = 250
        self.min_silence_duration_ms = 100
        self.window_size_samples = 512 if sampling_rate == 16000 else 256
        
        # State
        self.triggered = False
        self.current_probability = 0.0
        self.temp_end = 0
        self.current_speech = {}
        
        # Load model
        if model_path is None:
            # Default to local path or download
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, "silero_vad.onnx")
            
        if not os.path.exists(model_path):
            logger.warning(f"Silero VAD model not found at {model_path}. Attempting to download...")
            self._download_model(model_path)
            
        try:
            opts = onnxruntime.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            self.session = onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider'], sess_options=opts)
            self._h = np.zeros((2, 1, 64)).astype('float32')
            self._c = np.zeros((2, 1, 64)).astype('float32')
            logger.info("Silero VAD model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise

    def _download_model(self, path: str):
        import urllib.request
        url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
        try:
            urllib.request.urlretrieve(url, path)
            logger.info(f"Downloaded Silero VAD model to {path}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    def reset(self):
        """Reset VAD state."""
        self.triggered = False
        self.current_probability = 0.0
        self.temp_end = 0
        self.current_speech = {}
        self._h = np.zeros((2, 1, 64)).astype('float32')
        self._c = np.zeros((2, 1, 64)).astype('float32')

    def process_audio_chunk(self, audio_chunk: bytes) -> List[Dict[str, Any]]:
        """
        Process an audio chunk and return events (speech_start, speech_end).
        Assumes audio_chunk is 16-bit PCM.
        """
        # Convert bytes to float32 numpy array
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Add dimension for batch
        input_tensor = audio_float32[np.newaxis, :]
        
        # Run inference
        ort_inputs = {
            'input': input_tensor,
            'h': self._h,
            'c': self._c,
            'sr': np.array([self.sampling_rate], dtype=np.int64)
        }
        ort_outs = self.session.run(None, ort_inputs)
        out, self._h, self._c = ort_outs
        
        self.current_probability = out[0][0]
        
        events = []
        
        # Logic for triggering
        if self.current_probability >= self.threshold and self.temp_end:
            self.temp_end = 0
            
        if self.current_probability >= self.threshold and not self.triggered:
            self.triggered = True
            events.append({"type": "speech_start", "prob": float(self.current_probability)})
            
        if self.current_probability < (self.threshold - 0.15) and self.triggered:
            if not self.temp_end:
                self.temp_end = 1 # Start silence counter (simplified)
            else:
                # In a real implementation we'd count frames. 
                # For now, immediate switch off with hysteresis
                self.triggered = False
                self.temp_end = 0
                events.append({"type": "speech_end", "prob": float(self.current_probability)})
                
        return events
