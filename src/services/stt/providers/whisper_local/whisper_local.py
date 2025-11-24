"""
Whisper Local STT Provider

WebSocket client for connecting to the whisper-stt service for real-time
speech-to-text transcription.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Any

import websockets

from services.provider_constants import get_provider_constants

logger = logging.getLogger(__name__)


class WhisperLocalProvider:
    """
    STT provider that connects to whisper-stt service via WebSocket.
    """

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return []

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.
        
        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
        }

    def __init__(self, provider_config: dict = None):
        """
        Initialize Whisper Local STT provider using immutable constants.

        Configuration is now fully code-defined via WhisperLocalSTTConstants and
        does not depend on database-backed global configuration.
        
        Args:
            provider_config: Configuration dictionary (currently unused but kept for API consistency)
        """
        constants = get_provider_constants()
        self.websocket_url = constants['stt']['whisper.local']['URL']
        self.websocket_path = constants['stt']['whisper.local']['PATH']
        self.full_url = f"{self.websocket_url}{self.websocket_path}"
        self.websocket = None
        self.connected = False
        self.transcripts: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """Connect to the whisper-stt WebSocket service."""
        try:
            self.websocket = await websockets.connect(self.full_url)
            self.connected = True
            logger.info(f"Connected to whisper-stt service at {self.full_url}")
        except Exception as e:
            logger.error(f"Failed to connect to whisper-stt service: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the whisper-stt service."""
        if self.connected and self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Disconnected from whisper-stt service")


    async def _receive_transcripts(self) -> None:
        """Receive and store transcripts from the WebSocket connection."""
        try:
            # Remove the 10-second timeout - keep listening indefinitely for new transcripts
            # This allows the system to handle long pauses between user speech segments
            while True:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=0.5
                    )
                    
                    if message:
                        data = json.loads(message)
                        self.transcripts.append(data)
                        #logger.debug(f"Received transcript: {data}")
                        
                except asyncio.TimeoutError:
                    # Continue waiting indefinitely for new transcripts
                    # This allows the system to handle long pauses between user speech
                    continue
                    
        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving transcripts: {e}")

    async def stream_audio_chunks(
        self,
        audio_chunk_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
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
            # Track last transcript index to avoid duplicates
            last_transcript_index = 0

            # Process audio chunks as they arrive
            async for audio_chunk in audio_chunk_generator:
                if audio_chunk:
                    # Send chunk to provider
                    await self.websocket.send(audio_chunk)
                    
                    # Yield only new transcripts (avoid duplicates)
                    while len(self.transcripts) > last_transcript_index:
                        transcript = self.transcripts[last_transcript_index]
                        yield transcript
                        last_transcript_index += 1

            # Send end message
            await self.websocket.send(json.dumps({"text": "end"}))
            #logger.info("Sent end message to whisper-stt service")

            # Yield any remaining new transcripts
            while len(self.transcripts) > last_transcript_index:
                transcript = self.transcripts[last_transcript_index]
                yield transcript
                last_transcript_index += 1

        except Exception as e:
            logger.error(f"Error during audio chunk streaming: {e}")
            raise
        finally:
            # Cancel receive task
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass


    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()