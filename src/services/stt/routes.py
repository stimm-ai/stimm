"""
STT API Routes
"""

import asyncio
import logging
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .stt import STTService

logger = logging.getLogger(__name__)

router = APIRouter()
# Don't initialize STTService globally - create instances per request with agent_id


@router.websocket("/stt/ws")
async def stt_websocket(websocket: WebSocket, agent_id: str = None):
    """
    WebSocket endpoint for real-time STT operations.

    This endpoint:
    - Accepts WebSocket connections
    - Receives audio data in chunks
    - Streams transcription results in real-time
    - Handles connection lifecycle
    - Supports agent-based configuration via agent_id parameter
    """
    await websocket.accept()

    # Validate and normalize agent_id
    normalized_agent_id = None
    if agent_id and agent_id != "null" and agent_id != "undefined":
        try:
            from uuid import UUID

            normalized_agent_id = UUID(agent_id)
        except ValueError:
            logger.warning(f"Invalid agent_id format: {agent_id}, using default agent")

    logger.info(f"STT WebSocket connection established (agent_id: {normalized_agent_id})")

    try:
        # Create STT service instance with agent configuration
        stt_service = STTService(agent_id=normalized_agent_id)

        # Create an async generator for audio chunks
        async def audio_chunk_generator():
            while True:
                try:
                    message = await websocket.receive()

                    if "bytes" in message:
                        # Audio data received
                        audio_chunk = message["bytes"]
                        yield audio_chunk

                    elif "text" in message:
                        # Control message received
                        text_message = message["text"].strip().lower()

                        if text_message in ["close", "stop", "end"]:
                            logger.info("Received stop message, ending stream")
                            break
                        elif text_message == "flush":
                            # Continue processing
                            continue

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected during streaming")
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio chunk: {e}")
                    break

        # Use real streaming with the audio chunk generator
        async for transcript in stt_service.transcribe_streaming(audio_chunk_generator()):
            await websocket.send_json(transcript)

    except WebSocketDisconnect:
        logger.info("STT WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"STT WebSocket error: {e}")
        # Send error message to client
        try:
            await websocket.send_json({"error": str(e), "transcript": "", "is_final": True, "stability": 0.0})
        except Exception:  # nosec B110
            pass  # Client may have already disconnected
    finally:
        try:
            await websocket.close()
            logger.info("STT WebSocket connection closed")
        except Exception:  # nosec B110
            pass  # Connection may already be closed


@router.websocket("/stt/sync-stream")
async def stt_sync_streaming_websocket(websocket: WebSocket, agent_id: str = None):
    """
    Synchronized streaming WebSocket endpoint for real-time transcription.

    This endpoint:
    - Receives a start signal from frontend
    - Reads the test audio file with sounddevice
    - Streams audio chunks at correct timing (real-time speed)
    - Sends real-time transcription results
    - Supports agent-based configuration via agent_id parameter
    """
    await websocket.accept()

    # Validate and normalize agent_id
    normalized_agent_id = None
    if agent_id and agent_id != "null" and agent_id != "undefined":
        try:
            from uuid import UUID

            normalized_agent_id = UUID(agent_id)
        except ValueError:
            logger.warning(f"Invalid agent_id format: {agent_id}, using default agent")

    logger.info(f"STT sync streaming WebSocket connection established (agent_id: {normalized_agent_id})")

    # Constants for WebRTC-like streaming
    STREAM_SAMPLE_RATE = 16000
    CHUNK_DURATION_MS = 40  # 40ms chunks (typical WebRTC)
    CHUNK_SIZE = STREAM_SAMPLE_RATE * CHUNK_DURATION_MS // 1000

    # Test audio file path
    TEST_AUDIO_PATH = Path(__file__).parent.parent.parent / "services" / "stt" / "tests" / "Enregistrement.wav"

    try:
        # Wait for start signal from frontend
        start_message = await websocket.receive_text()
        if start_message.strip().lower() != "start":
            await websocket.send_json({"error": "Expected 'start' message", "transcript": "", "is_final": True, "stability": 0.0})
            return

        logger.info("Starting synchronized audio streaming")

        # Load audio file with soundfile
        audio_data, sample_rate = sf.read(TEST_AUDIO_PATH, dtype="float32")

        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        # Resample to 16kHz if needed
        if sample_rate != STREAM_SAMPLE_RATE:
            from scipy import signal

            audio_data = signal.resample(audio_data, int(len(audio_data) * STREAM_SAMPLE_RATE / sample_rate))

        # Convert to PCM16
        audio_data = (audio_data * 32767).astype(np.int16)

        # Create an async generator that streams audio in real-time
        async def audio_chunk_generator():
            chunk_samples = CHUNK_SIZE

            # Stream audio in real-time (like the tests do)
            for i in range(0, len(audio_data), chunk_samples):
                chunk = audio_data[i : i + chunk_samples].tobytes()
                yield chunk

                # Calculate real delay based on audio duration (real-time speed)
                chunk_duration = chunk_samples / STREAM_SAMPLE_RATE
                await asyncio.sleep(chunk_duration)

        # Create STT service instance with agent configuration
        stt_service = STTService(agent_id=normalized_agent_id)

        # Use real streaming with the audio chunk generator
        async for transcript in stt_service.transcribe_streaming(audio_chunk_generator()):
            await websocket.send_json(transcript)

        # Wait for the transcription to complete naturally
        # The transcribe_streaming method should handle end-of-transcription detection
        # based on the audio stream completion, so we don't need a fixed sleep

    except WebSocketDisconnect:
        logger.info("STT sync streaming WebSocket disconnected")
    except Exception as e:
        logger.error(f"STT sync streaming WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "transcript": "", "is_final": True, "stability": 0.0})
        except Exception:  # nosec B110
            pass  # Client may have already disconnected
    finally:
        # Don't close the connection automatically - let the frontend close it
        # after receiving the completion message
        logger.info("STT sync streaming processing completed")
