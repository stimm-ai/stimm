"""
Deepgram STT Provider

WebSocket client for connecting to Deepgram API for real-time
speech-to-text transcription using raw WebSocket API.
"""

import asyncio
import json
import logging
import urllib.parse
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from services.provider_constants import get_provider_constants

logger = logging.getLogger(__name__)


class DeepgramProvider:
    """
    STT provider that connects to Deepgram API via WebSocket using raw API.
    """

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["model", "api_key"]

    @classmethod
    def get_field_definitions(cls) -> dict:
        """Get field definitions for Deepgram STT provider."""
        return {
            "model": {
                "type": "text",
                "label": "Model",
                "required": True,
                "description": "Deepgram model name (e.g., nova-2)",
            },
            "api_key": {"type": "password", "label": "API Key", "required": True, "description": "Deepgram API key"},
            "language": {
                "type": "text",
                "label": "Language",
                "required": False,
                "description": "Language code (e.g., fr, en, es)",
            },
        }

    def __init__(self, provider_config: dict = None):
        # Use agent configuration for non-constant values (API keys, model, language)
        if provider_config:
            self.api_key = provider_config.get("api_key")
            self.model = provider_config.get("model", "nova-2")
            self.language = provider_config.get("language", "fr")

            # Validate required configuration
            if not self.api_key:
                raise ValueError("API key is required for DeepgramProvider")
            if not self.model:
                raise ValueError("Model is required for DeepgramProvider")
        else:
            # No fallback - agent configuration is required
            raise ValueError("Agent configuration is required for DeepgramProvider")

        self.websocket = None
        self.connected = False
        self.transcripts: List[Dict[str, Any]] = []
        self._transcript_queue = asyncio.Queue()

    async def connect(self) -> None:
        """Connect to the Deepgram WebSocket service."""
        try:
            if not self.api_key:
                raise ValueError("DEEPGRAM_STT_API_KEY environment variable is required")

            # Use immutable constants for provider configuration
            constants = get_provider_constants()
            base_url = constants["stt"]["deepgram.com"]["BASE_URL"]
            sample_rate = constants["stt"]["deepgram.com"]["SAMPLE_RATE"]

            # Build WebSocket URL with query parameters
            params = {
                "model": self.model,
                "language": self.language,
                "smart_format": "true",
                "encoding": "linear16",
                "sample_rate": sample_rate,
                "channels": "1",
                "interim_results": "true",
                "endpointing": "500",
                "vad_events": "true",
            }

            query_string = urllib.parse.urlencode(params)
            ws_url = f"{base_url.replace('https://', 'wss://').replace('http://', 'ws://')}/v1/listen?{query_string}"

            # Connect with authorization header using aiohttp
            headers = {"Authorization": f"Token {self.api_key}"}

            # Use aiohttp for WebSocket connection with proper headers
            self.session = aiohttp.ClientSession()
            self.websocket = await self.session.ws_connect(ws_url, headers=headers)
            self.connected = True
            logger.debug(f"Connected to Deepgram service with model: {self.model}, language: {self.language}")

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram service: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the Deepgram service."""
        if self.connected and self.websocket:
            try:
                # Send close stream message
                close_message = json.dumps({"type": "CloseStream"})
                await self.websocket.send_str(close_message)
                await self.websocket.close()
                self.connected = False
                logger.info("Disconnected from Deepgram service")
            except Exception as e:
                logger.error(f"Error disconnecting from Deepgram service: {e}")

        # Close the aiohttp session
        if self.session:
            await self.session.close()
            self.session = None

    async def _receive_transcripts(self) -> None:
        """Receive and process transcripts from the WebSocket connection."""
        try:
            while self.connected and not self.websocket.closed:
                try:
                    message = await asyncio.wait_for(self.websocket.receive(), timeout=1.0)

                    if message.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(message.data)
                        transcript_data = self._parse_transcript(data)
                        if transcript_data:
                            await self._transcript_queue.put(transcript_data)
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {message.data}")
                        self.connected = False
                        break
                    elif message.type == aiohttp.WSMsgType.CLOSE:
                        logger.info("WebSocket connection closed")
                        self.connected = False
                        break

                except asyncio.TimeoutError:
                    # Continue waiting for new messages
                    continue

        except Exception as e:
            logger.error(f"Error receiving transcripts: {e}")
            self.connected = False

    def _parse_transcript(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Deepgram transcript into standardized format."""
        try:
            message_type = data.get("type")

            if message_type == "Results":
                # Parse transcription results
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])

                if not alternatives:
                    return None

                alternative = alternatives[0]
                transcript_text = alternative.get("transcript", "").strip()

                if not transcript_text:
                    return None

                # Determine if this is a final transcript
                is_final = data.get("is_final", False)
                speech_final = data.get("speech_final", False)

                # Calculate confidence from words if available
                confidence = 0.0
                words = alternative.get("words", [])
                if words:
                    confidences = [word.get("confidence", 0.0) for word in words]
                    confidence = sum(confidences) / len(confidences) if confidences else 0.0
                else:
                    confidence = alternative.get("confidence", 0.0)

                return {
                    "transcript": transcript_text,
                    "is_final": is_final or speech_final,
                    "confidence": confidence,
                    "stability": data.get("stability", 0.0),
                    "provider": "deepgram",
                    "model": self.model,
                }

            elif message_type == "UtteranceEnd":
                # Handle utterance end events
                return {
                    "transcript": "",
                    "is_final": True,
                    "confidence": 0.0,
                    "stability": 0.0,
                    "provider": "deepgram",
                    "model": self.model,
                    "utterance_end": True,
                }

            elif message_type == "SpeechStarted":
                # Handle speech started events
                logger.debug("Speech started detected")
                return None

        except Exception as e:
            logger.error(f"Error parsing Deepgram transcript: {e}")

        return None

    async def stream_audio_chunks(self, audio_chunk_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream individual audio chunks and receive real-time transcripts.

        Args:
            audio_chunk_generator: Async generator yielding audio chunks

        Yields:
            Transcription results as dictionaries
        """
        if not self.connected:
            await self.connect()

        # Clear previous transcripts
        self.transcripts.clear()

        # Start receiving messages in background
        receive_task = asyncio.create_task(self._receive_transcripts())

        try:
            # Process audio chunks as they arrive
            async for audio_chunk in audio_chunk_generator:
                if audio_chunk and len(audio_chunk) > 0:
                    # Send audio chunk to Deepgram as binary
                    await self.websocket.send_bytes(audio_chunk)

                    # Yield any available transcripts from queue
                    while not self._transcript_queue.empty():
                        try:
                            transcript = await asyncio.wait_for(self._transcript_queue.get(), timeout=0.1)
                            yield transcript
                            self._transcript_queue.task_done()
                        except asyncio.TimeoutError:
                            break

            # Send finalize message to flush the stream
            finalize_message = json.dumps({"type": "Finalize"})
            await self.websocket.send_str(finalize_message)

            # Process any remaining transcripts
            while not self._transcript_queue.empty():
                try:
                    transcript = await asyncio.wait_for(self._transcript_queue.get(), timeout=0.1)
                    yield transcript
                    self._transcript_queue.task_done()
                except asyncio.TimeoutError:
                    break

        except Exception as e:
            logger.error(f"Error during audio chunk streaming: {e}")
            raise
        finally:
            # Cancel receive task and clean up
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

            # Disconnect
            if self.connected:
                await self.disconnect()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
