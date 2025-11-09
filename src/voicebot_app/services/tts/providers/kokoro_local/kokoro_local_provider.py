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

from services.provider_constants import get_provider_constants

logger = logging.getLogger(__name__)


class KokoroLocalProvider:
    """Kokoro Local TTS Provider with zero-latency audio resampling."""

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["voice", "language"]

    @classmethod
    def get_field_definitions(cls) -> dict:
        """
        Get field definitions for this provider.
        
        Returns:
            Dictionary of field definitions with type, label, and required status
        """
        return {
            "voice": {
                "type": "text",
                "label": "Voice",
                "required": True,
                "description": "Voice identifier for Kokoro TTS"
            },
            "language": {
                "type": "text",
                "label": "Language",
                "required": True,
                "description": "Language code for Kokoro TTS"
            }
            
        }

    def __init__(self, provider_config: dict = None):
        # Use agent configuration for non-constant values (voice, language)
        # Speed is NOT configurable - it's an immutable provider constant
        if provider_config:
            self.voice_id = provider_config.get("voice")
            self.language = provider_config.get("language")
        else:
            # No fallback - agent configuration is required
            raise ValueError("Agent configuration is required for KokoroLocalProvider")
        
        # Use immutable constants for provider configuration
        constants = get_provider_constants()
        self.websocket_url = constants['tts']['kokoro.local']['URL']
        self.input_sample_rate = constants['tts']['kokoro.local']['SAMPLE_RATE']
        self.encoding = constants['tts']['kokoro.local']['ENCODING']
        self.container = constants['tts']['kokoro.local']['CONTAINER']
        self.speed = constants['tts']['kokoro.local']['SPEED']  # Immutable constant, not configurable
        
        logger.info(f"KokoroLocalProvider initialized with URL: {self.websocket_url}, voice: {self.voice_id}, language: {self.language}, speed: {self.speed} (constant)")

    

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
                    resampled_item = item
                    chunk_count += 1
                    
                    logger.debug(f"Resampled audio chunk {chunk_count}: {len(item)} bytes → {len(resampled_item)} bytes")
                    yield resampled_item
            finally:
                send_task.cancel()
                recv_task.cancel()
                await asyncio.gather(send_task, recv_task, return_exceptions=True)