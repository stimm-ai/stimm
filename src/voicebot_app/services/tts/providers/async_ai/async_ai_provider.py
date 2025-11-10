"""
Async.AI TTS Provider (passthrough for TTSService concurrent streaming)
"""

import asyncio
import json
import logging
import base64
import uuid
from typing import AsyncGenerator, Dict, Any
import websockets

from services.provider_constants import get_provider_constants

logger = logging.getLogger(__name__)


class AsyncAIProvider:
    """Thin passthrough provider for Async.AI WebSocket TTS API."""

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["voice", "model", "api_key"]

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.
        
        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
            "voice": {
                "type": "text",
                "label": "Voice ID",
                "required": True,
                "description": "AsyncAI voice identifier"
            },
            "model": {
                "type": "text",
                "label": "Model ID",
                "required": True,
                "description": "AsyncAI model identifier (e.g., tts-1)"
            },
            "api_key": {
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "AsyncAI API key"
            }
        }

    def __init__(self, provider_config: dict = None):
        # Use agent configuration for non-constant values (API keys, voice/model IDs)
        if provider_config:
            logger.info(f"🔍 AsyncAIProvider received config: {provider_config}")
            self.api_key = provider_config.get("api_key")
            
            # Support both 'voice' and 'voice_id' keys for flexibility
            self.voice_id = provider_config.get("voice_id") or provider_config.get("voice")
            
            # model_id is required for AsyncAI, use a default if not provided
            self.model_id = provider_config.get("model_id") or "tts-1"
            
            logger.info(f"🔍 AsyncAIProvider parsed - api_key: {bool(self.api_key)}, voice_id: {self.voice_id}, model_id: {self.model_id}")
            
            # Validate required parameters
            if not self.api_key:
                raise ValueError("API key is required for AsyncAIProvider")
            if not self.voice_id:
                raise ValueError("Voice ID is required for AsyncAIProvider")
        else:
            # No fallback - agent configuration is required
            raise ValueError("Agent configuration is required for AsyncAIProvider")
        
        # Use immutable constants for provider configuration
        constants = get_provider_constants()
        self.websocket_url = constants['tts']['async.ai']['URL']
        self.sample_rate = constants['tts']['async.ai']['SAMPLE_RATE']
        self.encoding = constants['tts']['async.ai']['ENCODING']
        self.container = constants['tts']['async.ai']['CONTAINER']


    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Concurrent streaming passthrough for use by TTSService."""
        url = f"{self.websocket_url}?api_key={self.api_key}&version=v1"
        logger.info(f"Connecting to AsyncAI WebSocket: {url.split('?')[0]}...")

        async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=None) as ws:
            logger.info("WebSocket connected, sending initialization...")
            # Send initialization message (direct JSON object, not wrapped)
            init_payload = {
                "model_id": self.model_id,
                "voice": {"mode": "id", "id": self.voice_id},
                "output_format": {
                    "container": self.container,
                    "encoding": self.encoding,
                    "sample_rate": self.sample_rate,
                }
            }
            await ws.send(json.dumps(init_payload))
            logger.info(f"Sent initialization: {init_payload}")

            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def sender():
                try:
                    text_count = 0
                    async for chunk in text_generator:
                        text_count += 1
                        
                        # Parse the standardized JSON payload
                        try:
                            payload = json.loads(chunk)
                            text_content = payload.get("text", "")
                            if text_content and not text_content.endswith(" "):
                                text_content += " "
                            
                            # Convert our standard format to AsyncAI format
                            asyncai_payload = {
                                "transcript": text_content,
                                "voice": {"mode": "id", "id": self.voice_id}
                            }
                            await ws.send(json.dumps(asyncai_payload))
                            logger.info(f"Sent text chunk {text_count}: {text_content.strip()}")
                        except json.JSONDecodeError:
                            # Fallback: if it's plain text, use it directly
                            if not chunk.endswith(" "):
                                chunk += " "
                            asyncai_payload = {
                                "transcript": chunk,
                                "voice": {"mode": "id", "id": self.voice_id}
                            }
                            await ws.send(json.dumps(asyncai_payload))
                            logger.info(f"Sent text chunk {text_count}: {chunk.strip()} (converted from plain text)")
                    
                    # Send close connection message with voice parameter
                    close_payload = {
                        "transcript": "",
                        "voice": {"mode": "id", "id": self.voice_id}
                    }
                    await ws.send(json.dumps(close_payload))
                    logger.info("Sent close connection message")
                except Exception as e:
                    logger.error(f"Sender error: {e}")

            async def receiver():
                try:
                    message_count = 0
                    async for raw_msg in ws:
                        message_count += 1
                        msg = json.loads(raw_msg)
                        logger.info(f"Received message {message_count}: {list(msg.keys())}")
                        
                        if "audio" in msg:
                            audio_b64 = msg.get("audio")
                            if audio_b64:
                                audio_bytes = base64.b64decode(audio_b64)
                                logger.info(f"Audio chunk: {len(audio_bytes)} bytes")
                                await queue.put(audio_bytes)
                            if msg.get("final"):
                                logger.info("Received final message")
                                break
                        else:
                            logger.info(f"Non-audio message: {msg}")
                except Exception as e:
                    logger.error(f"Receiver error: {e}")
                finally:
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