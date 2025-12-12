"""
Hume.ai TTS Provider

WebSocket client for connecting to Hume.ai TTS API for real-time
text-to-speech synthesis using aiohttp WebSocket.
"""

import asyncio
import base64
import json
import logging
from typing import AsyncGenerator

import aiohttp

from services.provider_constants import get_provider_constants

logger = logging.getLogger(__name__)


class HumeProvider:
    """Hume.ai TTS Provider with WebSocket streaming support."""

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["voice", "api_key", "version"]

    def __init__(self, provider_config: dict = None):
        # Use agent configuration for non-constant values (API keys, voice IDs)
        if provider_config:
            self.api_key = provider_config.get("api_key")
            self.voice_id = provider_config.get("voice")
            self.version = provider_config.get("version", "2")  # Default to version 2

            # Validate required configuration
            if not self.api_key:
                raise ValueError("API key is required for HumeProvider")
            if not self.voice_id:
                raise ValueError("Voice ID is required for HumeProvider")
        else:
            # No fallback - agent configuration is required
            raise ValueError("Agent configuration is required for HumeProvider")

        # Use immutable constants for audio parameters
        constants = get_provider_constants()
        self.sample_rate = constants["tts"]["hume.ai"]["SAMPLE_RATE"]
        self.encoding = constants["tts"]["hume.ai"]["ENCODING"]
        self.session = None
        self.websocket = None
        logger.info(f"HumeProvider initialized with voice: {self.voice_id}, version: {self.version}, sample_rate: {self.sample_rate}Hz")

    @classmethod
    def get_field_definitions(cls) -> dict:
        """Get field definitions for Hume.ai provider."""
        return {
            "voice": {
                "type": "text",
                "label": "Voice ID",
                "required": True,
                "description": "Hume.ai voice identifier",
            },
            "api_key": {
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Hume.ai API key",
            },
            "version": {
                "type": "text",
                "label": "API Version",
                "required": False,
                "description": "Hume.ai API version (1 or 2)",
                "default": "2",
            },
        }

    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Stream synthesis using Hume.ai TTS WebSocket API with aiohttp."""
        if not self.api_key:
            raise ValueError("HUME_TTS_API_KEY environment variable is required")

        # Build WebSocket URL with query parameters
        url = "wss://api.hume.ai/v0/tts/stream/input"

        # Set query parameters for Hume.ai API
        params = {
            "api_key": self.api_key,
            "version": self.version,
            "instant_mode": "true",
            "format_type": "pcm",
        }

        logger.info(f"Connecting to Hume.ai TTS WebSocket: {url}...")

        # Connect using aiohttp WebSocket with query parameters
        self.session = aiohttp.ClientSession()
        try:
            self.websocket = await self.session.ws_connect(url, params=params)
            logger.debug(f"✅ Hume.ai TTS WebSocket connected to {url}")

            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def sender():
                try:
                    text_count = 0
                    async for text_chunk in text_generator:
                        text_count += 1

                        # Parse the standardized JSON payload
                        try:
                            # Handle case where text_chunk might be an integer or other non-string type
                            if not isinstance(text_chunk, str):
                                text_chunk = str(text_chunk)

                            payload = json.loads(text_chunk)
                            # Convert our standard format to Hume.ai format
                            hume_payload = {
                                "text": payload.get("text", "") + " ",  # Add space for continuity
                                "voice": {"id": self.voice_id},
                                "flush": payload.get("flush", False),
                            }
                            payload_str = json.dumps(hume_payload)
                            logger.debug(f"Sent text chunk {text_count}: '{payload.get('text', '').strip()}' (flush: {payload.get('flush', False)})")
                        except (json.JSONDecodeError, TypeError):
                            # Fallback: if it's not valid JSON, treat as plain text
                            text_content = str(text_chunk) if not isinstance(text_chunk, str) else text_chunk
                            standard_payload = {
                                "text": text_content + " ",  # Add space for continuity
                                "voice": {"id": self.voice_id},
                                "flush": False,
                            }
                            payload_str = json.dumps(standard_payload)
                            logger.debug(f"Sent text chunk {text_count}: '{text_content.strip()}' (converted from {type(text_chunk).__name__})")

                        try:
                            await self.websocket.send_str(payload_str)
                        except Exception as send_error:
                            logger.error(f"Failed to send text chunk {text_count}: {send_error}")
                            break

                    logger.debug(f"Text generator completed, sent {text_count} chunks total")

                    # Send final empty text with flush=True to indicate end
                    final_payload = {
                        "text": "",  # Empty string to indicate end
                        "voice": {"id": self.voice_id},
                        "flush": True,  # Flush the buffer - this is the final chunk
                    }
                    try:
                        await self.websocket.send_str(json.dumps(final_payload))
                        logger.debug("Sent final text chunk with flush=True")
                    except Exception as close_error:
                        logger.warning(f"Could not send final text chunk: {close_error}")

                    logger.info("Sender completed successfully")

                except Exception as e:
                    logger.error(f"Sender error: {e}")
                    import traceback

                    logger.error(f"Sender traceback: {traceback.format_exc()}")

            async def receiver():
                try:
                    chunk_count = 0
                    text_chunks_processed = 0
                    received_final_signal = False

                    async for msg in self.websocket:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                logger.debug(f"Received message: {list(data.keys())}")

                                # Check message type based on Hume.ai API structure
                                if "audio" in data:
                                    # Audio output message (base64 encoded)
                                    audio_b64 = data.get("audio")
                                    if audio_b64:
                                        audio_bytes = base64.b64decode(audio_b64)
                                        chunk_count += 1
                                        chunk_size = len(audio_bytes)

                                        logger.debug(f"Received audio chunk {chunk_count}: {chunk_size} bytes")
                                        logger.debug(f"🔊 Queuing audio chunk {chunk_count} ({chunk_size} bytes)")
                                        await queue.put(audio_bytes)

                                    # Handle is_last_chunk flag if present
                                    if data.get("is_last_chunk"):
                                        text_chunks_processed += 1
                                        logger.debug(f"Audio chunk {chunk_count} marked as last chunk (processed {text_chunks_processed} text chunks)")

                                elif "type" in data and data["type"] == "timestamp":
                                    # Timestamp message - ignore for audio streaming
                                    logger.debug(f"Received timestamp message: {data}")

                                elif "error" in data:
                                    # Error message from Hume.ai
                                    error_msg = data.get("error", "Unknown error")
                                    error_code = data.get("code", "Unknown code")
                                    logger.error(f"Hume.ai API error: {error_code} - {error_msg}")
                                    logger.error(f"Full error data: {data}")
                                    await queue.put(None)
                                    break

                                else:
                                    # Other message types
                                    logger.debug(f"Received non-audio message: {data}")

                            except json.JSONDecodeError:
                                logger.warning(f"Received non-JSON message: {msg.data}")
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            # Binary audio data (raw MP3/audio bytes)
                            audio_bytes = msg.data
                            chunk_count += 1
                            chunk_size = len(audio_bytes)
                            logger.debug(f"Received binary audio chunk {chunk_count}: {chunk_size} bytes")
                            logger.debug(f"🔊 Queuing binary audio chunk {chunk_count} ({chunk_size} bytes)")
                            await queue.put(audio_bytes)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {msg.data}")
                            await queue.put(None)
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSE:
                            logger.info("WebSocket connection closed")
                            # Only put None if we haven't already received the final signal
                            if not received_final_signal:
                                await queue.put(None)
                            break

                except Exception as e:
                    logger.error(f"Receiver error: {e}")
                    import traceback

                    logger.error(f"Receiver traceback: {traceback.format_exc()}")
                    await queue.put(None)

            send_task = asyncio.create_task(sender())
            recv_task = asyncio.create_task(receiver())

            try:
                chunk_count = 0
                while True:
                    item = await queue.get()
                    if item is None:
                        logger.info(f"Stream ended, yielded {chunk_count} audio chunks")
                        break
                    chunk_count += 1
                    yield item
            finally:
                send_task.cancel()
                recv_task.cancel()
                await asyncio.gather(send_task, recv_task, return_exceptions=True)

        finally:
            # Clean up WebSocket connection
            if self.websocket:
                await self.websocket.close()
            if self.session:
                await self.session.close()
