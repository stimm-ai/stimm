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
        self.context_size = 64 if sampling_rate == 16000 else 32
        
        # Audio buffering - accumulate chunks until we have window_size_samples
        self.audio_buffer = np.array([], dtype=np.float32)
        
        # State
        self.triggered = False
        self.current_probability = 0.0
        self.temp_end = 0
        self.current_speech = {}
        
        # Context for ONNX model (Silero needs previous context)
        self._context = np.zeros((1, self.context_size), dtype=np.float32)
        self._input_buffer = np.zeros((1, self.context_size + self.window_size_samples), dtype=np.float32)
        
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
            # V5 model uses a single state tensor of shape (2, 1, 128)
            self._state = np.zeros((2, 1, 128)).astype('float32')
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
        self._state = np.zeros((2, 1, 128)).astype('float32')
        self._context = np.zeros((1, self.context_size), dtype=np.float32)
        self.audio_buffer = np.array([], dtype=np.float32)  # Clear audio buffer

    def process_audio_chunk(self, audio_chunk: bytes) -> List[Dict[str, Any]]:
        """
        Process an audio chunk and return events (speech_start, speech_end).
        Assumes audio_chunk is 16-bit PCM.
        
        Buffers incoming audio until we have exactly window_size_samples (512 for 16kHz)
        before running inference, similar to LiveKit's implementation.
        """
        # Convert bytes to float32 numpy array
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Log audio statistics for first few chunks and when audio is loud
        if len(self.audio_buffer) < 1000 or np.max(np.abs(audio_int16)) > 1000:  # Log first chunks or loud audio
            logger.info(f"🔊 VAD input audio stats: len={len(audio_chunk)}, int16_range=[{np.min(audio_int16)}, {np.max(audio_int16)}], float32_range=[{np.min(audio_float32):.4f}, {np.max(audio_float32):.4f}]")
        
        # Accumulate audio in buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_float32])
        
        events = []
        windows_processed = 0
        
        # Process all complete windows in the buffer
        while len(self.audio_buffer) >= self.window_size_samples:
            # Extract exactly window_size_samples
            window = self.audio_buffer[:self.window_size_samples]
            
            # Keep remaining samples for next iteration
            self.audio_buffer = self.audio_buffer[self.window_size_samples:]
            
            # Prepare input with context
            # Matches LiveKit's implementation which improves detection
            self._input_buffer[:, :self.context_size] = self._context
            self._input_buffer[:, self.context_size:] = window[np.newaxis, :]
            
            # Run inference
            ort_inputs = {
                'input': self._input_buffer,
                'state': self._state,
                'sr': np.array(self.sampling_rate, dtype=np.int64)
            }
            ort_outs = self.session.run(None, ort_inputs)
            out, self._state = ort_outs
            
            # Update context for next frame
            self._context = self._input_buffer[:, -self.context_size:]
            
            self.current_probability = out[0][0]
            windows_processed += 1
            
            # TEMPORARY: Log every window for diagnosis
            logger.info(f"🎯 VAD window #{windows_processed}: prob={self.current_probability:.4f}, threshold={self.threshold:.3f}, triggered={self.triggered}")
            
            # Logic for triggering with hysteresis
            if self.current_probability >= self.threshold and self.temp_end:
                self.temp_end = 0
                logger.debug(f"🔄 VAD: Continuing speech (prob={self.current_probability:.3f})")
                
            if self.current_probability >= self.threshold and not self.triggered:
                self.triggered = True
                events.append({"type": "speech_start", "prob": float(self.current_probability)})
                logger.info(f"🗣️ VAD: Speech START detected! (prob={self.current_probability:.3f})")
                
            if self.current_probability < (self.threshold - 0.15) and self.triggered:
                if not self.temp_end:
                    self.temp_end = 1  # Start silence counter (simplified)
                    logger.debug(f"🤫 VAD: Silence detected, starting counter (prob={self.current_probability:.3f})")
                else:
                    # In a real implementation we'd count frames. 
                    # For now, immediate switch off with hysteresis
                    self.triggered = False
                    self.temp_end = 0
                    events.append({"type": "speech_end", "prob": float(self.current_probability)})
                    logger.info(f"🛑 VAD: Speech END detected! (prob={self.current_probability:.3f})")
        
        # Log buffer state periodically
        if windows_processed > 0:
            logger.debug(f"📊 VAD: Processed {windows_processed} windows, buffer remaining: {len(self.audio_buffer)} samples, events: {len(events)}")
                    
        return events
