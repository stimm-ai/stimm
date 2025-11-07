"""
Deepgram TTS Provider

WebSocket client for connecting to Deepgram TTS API for real-time
text-to-speech synthesis using aiohttp WebSocket.
"""

import asyncio
import json
import logging
import base64
from typing import AsyncGenerator
import aiohttp

from ...config import tts_config
from services.provider_constants import DeepgramTTSConstants

logger = logging.getLogger(__name__)


class DeepgramProvider:
    """Deepgram TTS Provider with WebSocket streaming support."""

    def __init__(self):
        self.config = tts_config
        self.session = None
        self.websocket = None
        logger.info("DeepgramProvider initialized")

    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Stream synthesis using Deepgram TTS WebSocket API with aiohttp.
        
        Uses hard-coded global defaults from DeepgramTTSDefaults plus agent/env config.
        """
        # Get agent-specific settings (api_key, model, etc.)
        agent_config = self.config.get_agent_config() if hasattr(self.config, 'get_agent_config') else {}
        api_key = agent_config.get("api_key") or self.config.deepgram_tts_api_key
        model = agent_config.get("model") or self.config.deepgram_model
        
        if not api_key:
            raise ValueError("Deepgram API key is required")

        # Use immutable constants for base URL and audio parameters
        base_url = DeepgramTTSConstants.BASE_URL
        sample_rate = DeepgramTTSConstants.SAMPLE_RATE
        encoding = DeepgramTTSConstants.ENCODING
        
        # Build WebSocket URL with query parameters
        url = f"{base_url.replace('https://', 'wss://').replace('http://', 'ws://')}/v1/speak?model={model}&encoding={encoding}&sample_rate={sample_rate}"
        
        # Set headers for authentication
        headers = {
            "Authorization": f"Token {api_key}"
        }
        
        logger.info(f"Connecting to Deepgram TTS WebSocket: {url}...")
        
        # Connect using aiohttp WebSocket
        self.session = aiohttp.ClientSession()
        try:
            self.websocket = await self.session.ws_connect(url, headers=headers)
            logger.info("Deepgram TTS WebSocket connected, starting text streaming...")

            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def sender():
                try:
                    text_count = 0
                    async for text_chunk in text_generator:
                        text_count += 1
                        # Send text message in Deepgram format
                        text_payload = {
                            "type": "Speak",
                            "text": text_chunk
                        }
                        await self.websocket.send_str(json.dumps(text_payload))
                        logger.info(f"Sent text chunk {text_count}: '{text_chunk.strip()}'")
                    
                    # Send flush message to get final audio
                    flush_payload = {
                        "type": "Flush"
                    }
                    await self.websocket.send_str(json.dumps(flush_payload))
                    logger.info("Sent flush message")
                    
                except Exception as e:
                    logger.error(f"Sender error: {e}")

            async def receiver():
                try:
                    chunk_count = 0
                    async for msg in self.websocket:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                msg_type = data.get("type")
                                
                                # Log all received messages for debugging
                                logger.debug(f"Received Deepgram message type: {msg_type}, data keys: {list(data.keys())}")
                                
                                if msg_type == "Metadata":
                                    logger.info(f"Received metadata: {data}")
                                elif msg_type == "Audio":
                                    # Audio data is base64 encoded in Deepgram response
                                    audio_b64 = data.get("audio")
                                    if audio_b64:
                                        audio_bytes = base64.b64decode(audio_b64)
                                        chunk_count += 1
                                        logger.info(f"Received audio chunk {chunk_count}: {len(audio_bytes)} bytes")
                                        await queue.put(audio_bytes)
                                    else:
                                        logger.warning(f"Audio message received but no 'audio' field found. Available fields: {list(data.keys())}")
                                elif msg_type == "Flushed":
                                    logger.info("Received flushed signal, stream complete")
                                    await queue.put(None)
                                    break
                                elif msg_type == "Warning":
                                    logger.warning(f"Deepgram warning: {data.get('description', 'Unknown warning')}")
                                elif msg_type == "Cleared":
                                    logger.info("Received cleared signal")
                                else:
                                    logger.warning(f"Unexpected message type: {msg_type}, full data: {data}")
                                    
                            except json.JSONDecodeError:
                                logger.warning(f"Received non-JSON message: {msg.data}")
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {msg.data}")
                            await queue.put(None)
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSE:
                            logger.info("WebSocket connection closed")
                            await queue.put(None)
                            break
                            
                except Exception as e:
                    logger.error(f"Receiver error: {e}")
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