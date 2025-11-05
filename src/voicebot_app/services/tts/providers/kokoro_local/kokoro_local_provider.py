"""
Kokoro Local TTS Provider with zero-latency audio resampling
"""

import asyncio
import json
import logging
import base64
from typing import AsyncGenerator
import websockets
import numpy as np
from scipy import signal

from ...config import tts_config

logger = logging.getLogger(__name__)


class KokoroLocalProvider:
    """Kokoro Local TTS Provider with zero-latency audio resampling."""

    def __init__(self):
        self.config = tts_config
        self.websocket_url = self.config.kokoro_local_url
        self.voice_id = self.config.kokoro_local_voice_id
        self.input_sample_rate = self.config.kokoro_local_sample_rate  # 24kHz from Kokoro
        self.output_sample_rate = 44100  # Target for frontend compatibility
        self.encoding = self.config.kokoro_local_encoding
        self.container = self.config.kokoro_local_container
        self.language = self.config.kokoro_local_language
        self.speed = self.config.kokoro_local_speed
        logger.info(f"KokoroLocalProvider initialized with URL: {self.websocket_url}, voice: {self.voice_id}, language: {self.language}, speed: {self.speed}")
        logger.info(f"Audio resampling: {self.input_sample_rate}Hz → {self.output_sample_rate}Hz")

    def _resample_audio_chunk(self, audio_data: bytes) -> bytes:
        """
        Resample audio chunk from 24kHz to 44.1kHz without adding latency.
        Uses linear interpolation for fast, real-time processing.
        """
        if not audio_data:
            return audio_data
        
        # Convert bytes to numpy array (16-bit PCM)
        samples_16bit = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to float32 for processing
        samples_float = samples_16bit.astype(np.float32) / 32768.0
        
        # Calculate resampling ratio
        ratio = self.output_sample_rate / self.input_sample_rate  # 44100/24000 = 1.8375
        
        # Calculate target number of samples
        target_length = int(len(samples_float) * ratio)
        
        # Use linear interpolation for zero-latency resampling
        # This is faster than scipy.signal.resample and suitable for real-time
        x_original = np.arange(len(samples_float))
        x_target = np.linspace(0, len(samples_float) - 1, target_length)
        resampled_float = np.interp(x_target, x_original, samples_float)
        
        # Convert back to 16-bit PCM
        resampled_16bit = (resampled_float * 32768.0).astype(np.int16)
        
        # Convert back to bytes
        return resampled_16bit.tobytes()

    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Live streaming synthesis using the new Kokoro live streaming endpoint."""
        # Use the new live streaming endpoint by default
        url = self.websocket_url.replace("/stream", "/live")
        logger.info(f"Connecting to Kokoro Live Streaming WebSocket: {url}...")

        async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=None) as ws:
            logger.info("Live streaming WebSocket connected, sending initialization...")
            
            # Send initialization for live streaming
            init_payload = {
                "voice": self.voice_id,
                "language": self.language,
                "speed": self.speed
            }
            await ws.send(json.dumps(init_payload))
            logger.info(f"Sent live streaming initialization: {init_payload}")

            # Wait for ready signal
            ready_msg = await ws.recv()
            ready_data = json.loads(ready_msg)
            if ready_data.get("type") != "ready":
                raise RuntimeError(f"Expected ready signal, got: {ready_data}")
            
            logger.info("Live streaming ready, starting text streaming...")

            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def sender():
                try:
                    text_count = 0
                    async for text_chunk in text_generator:
                        text_count += 1
                        
                        # Parse the standardized JSON payload
                        try:
                            payload = json.loads(text_chunk)
                            text_content = payload.get("text", "")
                            # Send text chunk directly (no JSON wrapper needed for live streaming)
                            await ws.send(text_content)
                            logger.info(f"Sent live text chunk {text_count}: '{text_content.strip()}'")
                        except json.JSONDecodeError:
                            # Fallback: if it's plain text, use it directly
                            await ws.send(text_chunk)
                            logger.info(f"Sent live text chunk {text_count}: '{text_chunk.strip()}' (converted from plain text)")
                    
                    # Send end signal
                    await ws.send("")
                    logger.info("Sent live streaming end signal")
                except Exception as e:
                    logger.error(f"Live streaming sender error: {e}")

            async def receiver():
                try:
                    chunk_count = 0
                    while True:
                        # First receive control message (should be JSON)
                        control_msg = await ws.recv()
                        
                        # Check if this is binary data (audio) or JSON (control)
                        if isinstance(control_msg, bytes):
                            # This is binary audio data, not a control message
                            chunk_count += 1
                            logger.info(f"Received live audio chunk {chunk_count}: {len(control_msg)} bytes")
                            await queue.put(control_msg)
                        else:
                            # This is a JSON control message
                            try:
                                control_data = json.loads(control_msg)
                                
                                if control_data.get("type") == "audio":
                                    # The next message should be binary audio data
                                    audio_data = await ws.recv()
                                    if isinstance(audio_data, bytes):
                                        chunk_count += 1
                                        logger.info(f"Received live audio chunk {chunk_count}: {len(audio_data)} bytes")
                                        await queue.put(audio_data)
                                elif control_data.get("type") == "end":
                                    logger.info(f"Live streaming completed: {chunk_count} audio chunks")
                                    await queue.put(None)
                                    break
                                elif control_data.get("type") == "error":
                                    error_msg = control_data.get("message", "Unknown error")
                                    logger.error(f"Live streaming error: {error_msg}")
                                    raise RuntimeError(f"Live streaming error: {error_msg}")
                                else:
                                    logger.warning(f"Unexpected control message: {control_data}")
                            except json.JSONDecodeError:
                                # If it's not valid JSON, it might be binary data
                                if isinstance(control_msg, bytes):
                                    chunk_count += 1
                                    logger.info(f"Received live audio chunk {chunk_count}: {len(control_msg)} bytes")
                                    await queue.put(control_msg)
                                else:
                                    logger.warning(f"Received unexpected non-JSON message: {control_msg}")
                            
                except Exception as e:
                    logger.error(f"Live streaming receiver error: {e}")
                    await queue.put(None)

            send_task = asyncio.create_task(sender())
            recv_task = asyncio.create_task(receiver())

            try:
                chunk_count = 0
                while True:
                    item = await queue.get()
                    if item is None:
                        logger.info(f"Live stream ended, yielded {chunk_count} audio chunks")
                        break
                    
                    # Apply real-time resampling to each audio chunk
                    resampled_item = self._resample_audio_chunk(item)
                    chunk_count += 1
                    
                    logger.debug(f"Resampled audio chunk {chunk_count}: {len(item)} bytes → {len(resampled_item)} bytes")
                    yield resampled_item
            finally:
                send_task.cancel()
                recv_task.cancel()
                await asyncio.gather(send_task, recv_task, return_exceptions=True)