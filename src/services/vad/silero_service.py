import asyncio
import logging
import os
import time
from typing import Any, Dict, List

import numpy as np
import onnxruntime

logger = logging.getLogger(__name__)


class VADOptions:
    def __init__(
        self,
        min_speech_duration: float = 0.05,
        min_silence_duration: float = 0.4,
        prefix_padding_duration: float = 0.5,
        max_buffered_speech: float = 60.0,
        activation_threshold: float = 0.5,
        sample_rate: int = 16000,
    ):
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        self.prefix_padding_duration = prefix_padding_duration
        self.max_buffered_speech = max_buffered_speech
        self.activation_threshold = activation_threshold
        self.sample_rate = sample_rate


class VADStream:
    """
    Stream processor for Silero VAD.
    Maintains state and buffers for a single audio stream.
    """

    def __init__(self, session: onnxruntime.InferenceSession, opts: VADOptions):
        self._session = session
        self._opts = opts

        # State
        self._triggered = False
        self._current_probability = 0.0
        self._speech_buffer_index = 0
        self._speech_buffer_max_reached = False

        # Buffers
        # 16kHz sample rate for internal processing
        self.window_size_samples = 512 if opts.sample_rate == 16000 else 256
        self.context_size = 64 if opts.sample_rate == 16000 else 32

        # Buffer for raw bytes (more efficient than numpy concat)
        self._raw_buffer = bytearray()
        self._window_size_bytes = self.window_size_samples * 2  # 16-bit audio

        # Internal buffers
        self._context = np.zeros((1, self.context_size), dtype=np.float32)
        self._state = np.zeros((2, 1, 128)).astype("float32")
        self._input_buffer = np.zeros((1, self.context_size + self.window_size_samples), dtype=np.float32)

        # Speech tracking
        self._speech_start_timestamp = 0.0
        self._speech_duration = 0.0
        self._silence_duration = 0.0

        # Performance monitoring
        self._last_inference_time = 0
        self._slow_inference_count = 0

    @property
    def triggered(self) -> bool:
        return self._triggered

    @property
    def current_probability(self) -> float:
        return self._current_probability

    async def process_audio_chunk(self, audio_chunk: bytes) -> List[Dict[str, Any]]:
        """
        Process an audio chunk and return events.
        """
        # Append to raw buffer
        self._raw_buffer.extend(audio_chunk)

        events = []

        while len(self._raw_buffer) >= self._window_size_bytes:
            # Extract window bytes
            window_bytes = self._raw_buffer[: self._window_size_bytes]
            del self._raw_buffer[: self._window_size_bytes]

            # Convert to float32 only when we have a full window
            audio_int16 = np.frombuffer(window_bytes, dtype=np.int16)
            window = audio_int16.astype(np.float32) / 32768.0

            # Prepare input
            self._input_buffer[:, : self.context_size] = self._context
            self._input_buffer[:, self.context_size :] = window[np.newaxis, :]

            # Run inference in thread pool
            start_time = time.perf_counter()
            prob = await self._run_inference()
            inference_duration = time.perf_counter() - start_time

            self._current_probability = prob

            if inference_duration > 0.02:  # Log if inference takes > 20ms
                self._slow_inference_count += 1
                if self._slow_inference_count % 100 == 0:
                    logger.warning(f"VAD Inference slow: {inference_duration * 1000:.2f}ms")

            # Update context
            self._context = self._input_buffer[:, -self.context_size :]

            # Process probability
            new_events = self._process_probability(prob)
            events.extend(new_events)

        return events

    async def _run_inference(self) -> float:
        ort_inputs = {
            "input": self._input_buffer,
            "state": self._state,
            "sr": np.array(self._opts.sample_rate, dtype=np.int64),
        }

        # Run in executor to avoid blocking event loop
        try:
            loop = asyncio.get_running_loop()
            ort_outs = await loop.run_in_executor(None, lambda: self._session.run(None, ort_inputs))
            out, self._state = ort_outs
            return float(out[0][0])
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return 0.0

    def _process_probability(self, prob: float) -> List[Dict[str, Any]]:
        events = []
        window_duration = self.window_size_samples / self._opts.sample_rate

        if prob >= self._opts.activation_threshold:
            self._speech_duration += window_duration
            self._silence_duration = 0.0

            if not self._triggered and self._speech_duration >= self._opts.min_speech_duration:
                self._triggered = True
                events.append({"type": "speech_start", "prob": prob, "timestamp": time.time()})
        else:
            self._silence_duration += window_duration
            self._speech_duration = 0.0

            if self._triggered and self._silence_duration >= self._opts.min_silence_duration:
                self._triggered = False
                events.append({"type": "speech_end", "prob": prob, "timestamp": time.time()})

        return events

    def reset(self):
        self._triggered = False
        self._current_probability = 0.0
        self._state = np.zeros((2, 1, 128)).astype("float32")
        self._context = np.zeros((1, self.context_size), dtype=np.float32)
        self._raw_buffer = bytearray()
        self._speech_duration = 0.0
        self._silence_duration = 0.0


class SileroVADService:
    """
    Factory service for Silero VAD.
    Also provides a default stream for backward compatibility.
    """

    def __init__(self, model_path: str = None, threshold: float = 0.5):
        self.threshold = threshold
        self.sample_rate = 16000

        # Load model
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, "silero_vad.onnx")

        if not os.path.exists(model_path):
            logger.warning(f"Silero VAD model not found at {model_path}. Attempting to download...")
            self._download_model(model_path)

        try:
            opts = onnxruntime.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            # Enable graph optimization
            opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"], sess_options=opts)
            logger.info("Silero VAD model loaded successfully (Optimized Service V2)")

            # Initialize default stream for backward compatibility
            self._default_stream = self.create_stream()

        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise

    def _download_model(self, path: str):
        import urllib.request
        from urllib.parse import urlparse

        url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
        try:
            # Validate URL scheme for security
            parsed_url = urlparse(url)
            if parsed_url.scheme not in ["http", "https"]:
                raise ValueError(f"Unsupported URL scheme: {parsed_url.scheme}")

            # Use urlretrieve with security considerations
            # URL scheme validation already performed above, download from trusted source
            urllib.request.urlretrieve(url, path)
            logger.info(f"Downloaded Silero VAD model to {path}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    def create_stream(self, threshold: float = None) -> VADStream:
        """Create a new VAD stream processor"""
        opts = VADOptions(activation_threshold=threshold or self.threshold, sample_rate=self.sample_rate)
        return VADStream(self.session, opts)

    # --- Backward Compatibility Layer ---

    @property
    def triggered(self) -> bool:
        """Backward compatibility property"""
        return self._default_stream.triggered

    @property
    def current_probability(self) -> float:
        """Backward compatibility property"""
        return self._default_stream.current_probability

    async def process_audio_chunk(self, audio_chunk: bytes) -> List[Dict[str, Any]]:
        """Backward compatibility method"""
        return await self._default_stream.process_audio_chunk(audio_chunk)

    def reset(self):
        """Backward compatibility method"""
        self._default_stream.reset()
