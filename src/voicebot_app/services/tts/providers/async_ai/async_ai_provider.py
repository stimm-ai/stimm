"""
Async.AI TTS Provider (passthrough for TTSService concurrent streaming)
"""

import asyncio
import json
import logging
import base64
from typing import AsyncGenerator
import websockets

from ...config import tts_config
from services.provider_constants import AsyncAITTSConstants

logger = logging.getLogger(__name__)


class AsyncAIProvider:
    """Thin passthrough provider for Async.AI WebSocket TTS API."""

    def __init__(self):
        self.config = tts_config
        # Use immutable constants for provider configuration
        self.websocket_url = AsyncAITTSConstants.URL
        self.api_key = self.config.async_ai_api_key
        self.voice_id = self.config.async_ai_voice_id
        self.model_id = self.config.async_ai_model_id
        self.sample_rate = AsyncAITTSConstants.SAMPLE_RATE
        self.encoding = AsyncAITTSConstants.ENCODING
        self.container = AsyncAITTSConstants.CONTAINER


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
                            asyncai_payload = {"transcript": text_content}
                            await ws.send(json.dumps(asyncai_payload))
                            logger.info(f"Sent text chunk {text_count}: {text_content.strip()}")
                        except json.JSONDecodeError:
                            # Fallback: if it's plain text, use it directly
                            if not chunk.endswith(" "):
                                chunk += " "
                            await ws.send(json.dumps({"transcript": chunk}))
                            logger.info(f"Sent text chunk {text_count}: {chunk.strip()} (converted from plain text)")
                    
                    # Send close connection message as {"transcript": ""}
                    await ws.send(json.dumps({"transcript": ""}))
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