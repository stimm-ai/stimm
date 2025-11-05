
"""
ElevenLabs TTS Provider

WebSocket client for connecting to ElevenLabs TTS API for real-time
text-to-speech synthesis using aiohttp WebSocket.
"""

import asyncio
import json
import logging
import base64
from typing import AsyncGenerator
import aiohttp

from ...config import tts_config

logger = logging.getLogger(__name__)


class ElevenLabsProvider:
    """ElevenLabs TTS Provider with WebSocket streaming support."""

    def __init__(self):
        self.config = tts_config
        self.api_key = self.config.elevenlabs_api_key
        self.voice_id = self.config.elevenlabs_voice_id
        self.model_id = self.config.elevenlabs_model_id
        self.sample_rate = self.config.elevenlabs_sample_rate
        self.encoding = self.config.elevenlabs_encoding
        self.output_format = self.config.elevenlabs_output_format
        self.session = None
        self.websocket = None
        logger.info(f"ElevenLabsProvider initialized with voice: {self.voice_id}, model: {self.model_id}, sample_rate: {self.sample_rate}Hz")

    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Stream synthesis using ElevenLabs TTS WebSocket API with aiohttp."""
        if not self.api_key:
            raise ValueError("ELEVENLABS_TTS_API_KEY environment variable is required")

        # Build WebSocket URL with query parameters
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input"
        
        # Set query parameters (all values must be strings)
        params = {
            "model_id": self.model_id,
            "output_format": self.output_format,
            "enable_logging": "false",     # Reduce logging for performance
            "inactivity_timeout": "300",   # Longer timeout for continuous streaming
            "sync_alignment": "false",     # Disable alignment for smoother flow
            "auto_mode": "false",          # Manual control of generation triggering
            "apply_text_normalization": "auto"
        }
        
        # Set headers for authentication
        headers = {
            "xi-api-key": self.api_key
        }
        
        logger.info(f"Connecting to ElevenLabs TTS WebSocket: {url}...")
        
        # Connect using aiohttp WebSocket with query parameters
        self.session = aiohttp.ClientSession()
        try:
            self.websocket = await self.session.ws_connect(url, headers=headers, params=params)
            logger.info("ElevenLabs TTS WebSocket connected, sending initialization...")
            
            # Send initialization message
            init_payload = {
                "text": " ",  # Required: single space for initialization
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
                # Note: xi-api-key is NOT included in the initialization payload
                # It's only in the headers/query parameters
            }
            await self.websocket.send_str(json.dumps(init_payload))
            logger.info("Sent initialization message")

            queue: asyncio.Queue[bytes | None] = asyncio.Queue()

            async def sender():
                try:
                    text_count = 0
                    async for text_chunk in text_generator:
                        text_count += 1
                        
                        # Parse the standardized JSON payload
                        try:
                            payload = json.loads(text_chunk)
                            # Convert our standard format to ElevenLabs format
                            elevenlabs_payload = {
                                "text": payload.get("text", "") + " ",  # Add space for continuity
                                "try_trigger_generation": False,        # Disable auto generation triggering
                                "flush": payload.get("flush", False)
                            }
                            payload_str = json.dumps(elevenlabs_payload)
                            logger.info(f"Sent text chunk {text_count}: '{payload.get('text', '').strip()}' (flush: {payload.get('flush', False)})")
                        except json.JSONDecodeError:
                            # Fallback: if it's plain text, wrap it in our standard format
                            standard_payload = {
                                "text": text_chunk + " ",  # Add space for continuity
                                "try_trigger_generation": False,  # Disable auto generation triggering
                                "flush": False
                            }
                            payload_str = json.dumps(standard_payload)
                            logger.info(f"Sent text chunk {text_count}: '{text_chunk.strip()}' (converted from plain text)")
                        
                        try:
                            await self.websocket.send_str(payload_str)
                        except Exception as send_error:
                            logger.error(f"Failed to send text chunk {text_count}: {send_error}")
                            break
                    
                    logger.info(f"Text generator completed, sent {text_count} chunks total")
                    
                    # Send final empty text with flush=True to indicate end
                    final_payload = {
                        "text": "",  # Empty string to indicate end
                        "try_trigger_generation": True,
                        "flush": True  # Flush the buffer - this is the final chunk
                    }
                    try:
                        await self.websocket.send_str(json.dumps(final_payload))
                        logger.info("Sent final text chunk with flush=True")
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
                    text_chunks_sent = 0
                    text_chunks_processed = 0
                    received_final_signal = False
                    
                    async for msg in self.websocket:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                logger.debug(f"Received message: {list(data.keys())}")
                                
                                # Check message type
                                if "audio" in data:
                                    # Audio output message
                                    audio_b64 = data.get("audio")
                                    if audio_b64:
                                        audio_bytes = base64.b64decode(audio_b64)
                                        chunk_count += 1
                                        chunk_size = len(audio_bytes)
                                        
                                        # Log detailed information about the chunk
                                        has_alignment = "alignment" in data
                                        has_normalized_alignment = "normalizedAlignment" in data
                                        is_final = data.get("isFinal", False)
                                        
                                        logger.info(f"Received audio chunk {chunk_count}: {chunk_size} bytes "
                                                   f"(alignment: {has_alignment}, normalizedAlignment: {has_normalized_alignment}, isFinal: {is_final})")
                                        
                                        # For now, accept all audio chunks to see what we receive
                                        # We'll add filtering later based on actual observation
                                        await queue.put(audio_bytes)
                                    
                                    # Handle isFinal flag - ElevenLabs sends this with each audio chunk
                                    # Note: isFinal with audio means this chunk is final for the current text segment
                                    # but more audio chunks may come for other segments
                                    if data.get("isFinal"):
                                        text_chunks_processed += 1
                                        logger.debug(f"Audio chunk {chunk_count} marked as final (processed {text_chunks_processed} text chunks)")
                                    
                                elif "isFinal" in data and data["isFinal"]:
                                    # Final output message (no audio) - this is the real end signal
                                    logger.info("Received final output signal (no audio) - ending stream")
                                    received_final_signal = True
                                    await queue.put(None)
                                    break
                                    
                                elif "error" in data:
                                    # Error message from ElevenLabs
                                    error_msg = data.get("error", "Unknown error")
                                    error_code = data.get("code", "Unknown code")
                                    logger.error(f"ElevenLabs API error: {error_code} - {error_msg}")
                                    logger.error(f"Full error data: {data}")
                                    await queue.put(None)
                                    break
                                    
                                else:
                                    # Other message types (alignment data, etc.)
                                    logger.debug(f"Received non-audio message: {data}")
                                    
                            except json.JSONDecodeError:
                                logger.warning(f"Received non-JSON message: {msg.data}")
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
