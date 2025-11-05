"""FastAPI service exposing Kokoro ONNX text-to-speech with streaming output."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from kokoro_onnx import Kokoro

LOGGER = logging.getLogger("kokoro_tts_service")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Kokoro TTS Service",
    description="Self-hosted Kokoro ONNX text-to-speech backend with streaming WAV responses.",
    version="0.1.0",
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid integer for %s=%r; defaulting to %d", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid float for %s=%r; defaulting to %.2f", name, raw, default)
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

MODEL_PATH = Path(os.getenv("KOKORO_MODEL_PATH", "/models/kokoro/kokoro-v1.0.onnx"))
VOICES_PATH = Path(os.getenv("KOKORO_VOICES_PATH", "/models/kokoro/voices-v1.0.bin"))
MODEL_URL = os.getenv(
    "KOKORO_MODEL_URL",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
)
VOICES_URL = os.getenv(
    "KOKORO_VOICES_URL",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
)

DEFAULT_LANGUAGE = _env_str("KOKORO_TTS_DEFAULT_LANGUAGE", "en-US")
DEFAULT_VOICE = _env_str("KOKORO_TTS_DEFAULT_VOICE", "af_sarah")
DEFAULT_SPEED = _clamp(_env_float("KOKORO_TTS_DEFAULT_SPEED", 1.0), 0.5, 2.0)
DEFAULT_SAMPLE_RATE = _env_int("KOKORO_TTS_SAMPLE_RATE", 22050)
DEFAULT_BLEND_RATIO = _clamp(_env_float("KOKORO_TTS_BLEND_RATIO", 0.5), 0.0, 1.0)

PCM_SAMPLE_WIDTH_BYTES = 2
PCM_CHANNELS = 1

_kokoro_model: Optional[Kokoro] = None
_model_lock = asyncio.Lock()


def _ensure_asset(path: Path, url: str) -> None:
    if path.exists():
        return
    if not url:
        raise RuntimeError(f"Missing download URL for asset {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading Kokoro asset %s", path.name)
    try:
        with urllib.request.urlopen(url) as source, path.open("wb") as target:
            shutil.copyfileobj(source, target)
    except Exception as exc:  # pragma: no cover - network dependent
        if path.exists():
            path.unlink(missing_ok=True)
        raise RuntimeError(f"Unable to download {path.name} from {url}: {exc}") from exc


async def _load_model() -> Kokoro:
    global _kokoro_model
    if _kokoro_model is not None:
        return _kokoro_model

    async with _model_lock:
        if _kokoro_model is not None:
            return _kokoro_model

        loop = asyncio.get_running_loop()

        def _init() -> Kokoro:
            _ensure_asset(MODEL_PATH, MODEL_URL)
            _ensure_asset(VOICES_PATH, VOICES_URL)
            LOGGER.info("Loading Kokoro model from %s", MODEL_PATH)
            return Kokoro(str(MODEL_PATH), str(VOICES_PATH))

        model = await loop.run_in_executor(None, _init)
        LOGGER.info("Kokoro voices available: %d", len(model.get_voices()))
        _kokoro_model = model
        return model


def _build_wav_stream_header(sample_rate: int) -> bytes:
    bits_per_sample = PCM_SAMPLE_WIDTH_BYTES * 8
    byte_rate = sample_rate * PCM_CHANNELS * PCM_SAMPLE_WIDTH_BYTES
    block_align = PCM_CHANNELS * PCM_SAMPLE_WIDTH_BYTES
    return (
        b"RIFF"
        + (0xFFFFFFFF).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")  # PCM
        + PCM_CHANNELS.to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + byte_rate.to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + bits_per_sample.to_bytes(2, "little")
        + b"data"
        + (0xFFFFFFFF).to_bytes(4, "little")
    )


def _audio_to_pcm16(audio: np.ndarray) -> bytes:
    if audio.size == 0:
        return b""
    clipped = np.clip(audio.astype(np.float32), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    return pcm.tobytes()


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = None
    voice: Optional[str] = None
    speaker_id: Optional[str] = None
    sample_rate: Optional[int] = None
    speed: Optional[float] = None
    blend_with: Optional[str] = None
    blend_ratio: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


@dataclass
class SynthesisContext:
    text: str
    language: str
    voice: str
    blend_with: Optional[str]
    blend_ratio: float
    speed: float
    requested_sample_rate: int


def _resolve_synthesis_context(request: TTSRequest) -> SynthesisContext:
    metadata = request.metadata or {}
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text input cannot be empty")

    language = (request.language or metadata.get("language") or DEFAULT_LANGUAGE).strip()
    if not language:
        language = DEFAULT_LANGUAGE
    language = language.replace("_", "-").lower()

    voice = (request.voice or request.speaker_id or metadata.get("voice") or DEFAULT_VOICE).strip()
    if not voice:
        raise HTTPException(status_code=400, detail="Voice not provided")

    blend_with = (request.blend_with or metadata.get("blend_with") or metadata.get("kokoro_blend_with") or "").strip()
    if not blend_with:
        blend_with = None

    ratio_hint = request.blend_ratio if request.blend_ratio is not None else metadata.get("blend_ratio")
    if ratio_hint is None:
        ratio_hint = metadata.get("kokoro_blend_ratio")
    blend_ratio = _clamp(_coerce_float(ratio_hint, DEFAULT_BLEND_RATIO), 0.0, 1.0)

    speed = _coerce_float(request.speed or metadata.get("speed") or metadata.get("tts_speed"), DEFAULT_SPEED)
    speed = _clamp(speed, 0.5, 2.0)

    requested_sample_rate = request.sample_rate or metadata.get("sample_rate") or DEFAULT_SAMPLE_RATE
    try:
        requested_sample_rate = int(requested_sample_rate)
    except (TypeError, ValueError):
        requested_sample_rate = DEFAULT_SAMPLE_RATE

    return SynthesisContext(
        text=text,
        language=language,
        voice=voice,
        blend_with=blend_with,
        blend_ratio=blend_ratio,
        speed=speed,
        requested_sample_rate=requested_sample_rate,
    )


async def _render_stream(model: Kokoro, ctx: SynthesisContext) -> AsyncGenerator[bytes, None]:
    voice_argument: str | np.ndarray
    if ctx.blend_with:
        try:
            primary = model.get_voice_style(ctx.voice)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Unknown voice '{ctx.voice}'") from exc
        try:
            secondary = model.get_voice_style(ctx.blend_with)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Unknown blend voice '{ctx.blend_with}'") from exc
        voice_argument = (primary * (1.0 - ctx.blend_ratio)) + (secondary * ctx.blend_ratio)
    else:
        voice_argument = ctx.voice

    header_sent = False
    try:
        async for samples, sample_rate in model.create_stream(
            ctx.text,
            voice=voice_argument,
            speed=ctx.speed,
            lang=ctx.language,
        ):
            if not header_sent:
                yield _build_wav_stream_header(sample_rate)
                header_sent = True
            chunk = _audio_to_pcm16(samples)
            if chunk:
                yield chunk
    except AssertionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not header_sent:
        # Return an empty WAV payload to signal completion.
        yield _build_wav_stream_header(DEFAULT_SAMPLE_RATE)


@dataclass
class WebSocketSynthesisContext:
    text: str
    language: str
    voice: str
    blend_with: Optional[str]
    blend_ratio: float
    speed: float
    requested_sample_rate: int


def _resolve_websocket_context(data: Dict[str, Any]) -> WebSocketSynthesisContext:
    """Parse WebSocket message data into synthesis context."""
    text = (data.get("text", "") or "").strip()
    if not text:
        raise ValueError("Text input cannot be empty")

    language = (data.get("language") or data.get("metadata", {}).get("language") or DEFAULT_LANGUAGE).strip()
    if not language:
        language = DEFAULT_LANGUAGE
    language = language.replace("_", "-").lower()

    voice = (data.get("voice") or data.get("speaker_id") or data.get("metadata", {}).get("voice") or DEFAULT_VOICE).strip()
    if not voice:
        raise ValueError("Voice not provided")

    blend_with = (data.get("blend_with") or data.get("metadata", {}).get("blend_with") or "").strip()
    if not blend_with:
        blend_with = None

    ratio_hint = data.get("blend_ratio")
    if ratio_hint is None and data.get("metadata"):
        ratio_hint = data.get("metadata", {}).get("blend_ratio")
    blend_ratio = _clamp(_coerce_float(ratio_hint, DEFAULT_BLEND_RATIO), 0.0, 1.0)

    speed = _coerce_float(data.get("speed") or data.get("metadata", {}).get("speed"), DEFAULT_SPEED)
    speed = _clamp(speed, 0.5, 2.0)

    requested_sample_rate = data.get("sample_rate") or data.get("metadata", {}).get("sample_rate") or DEFAULT_SAMPLE_RATE
    try:
        requested_sample_rate = int(requested_sample_rate)
    except (TypeError, ValueError):
        requested_sample_rate = DEFAULT_SAMPLE_RATE

    return WebSocketSynthesisContext(
        text=text,
        language=language,
        voice=voice,
        blend_with=blend_with,
        blend_ratio=blend_ratio,
        speed=speed,
        requested_sample_rate=requested_sample_rate,
    )


async def handle_websocket_connection(websocket: WebSocket):
    """Handle WebSocket connection for TTS streaming."""
    await websocket.accept()
    LOGGER.info("WebSocket connection established")
    
    try:
        # Load model if not already loaded
        model = await _load_model()
        
        while True:
            # Wait for TTS request
            data = await websocket.receive_json()
            LOGGER.info("Received TTS request: %s", data.get("text", "")[:50] + "...")
            
            try:
                # Parse request
                ctx = _resolve_websocket_context(data)
                
                # Prepare voice argument
                voice_argument: str | np.ndarray
                if ctx.blend_with:
                    try:
                        primary = model.get_voice_style(ctx.voice)
                    except KeyError as exc:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown voice '{ctx.voice}'"
                        })
                        continue
                    try:
                        secondary = model.get_voice_style(ctx.blend_with)
                    except KeyError as exc:
                        await websocket.send_json({
                            "type": "error", 
                            "message": f"Unknown blend voice '{ctx.blend_with}'"
                        })
                        continue
                    voice_argument = (primary * (1.0 - ctx.blend_ratio)) + (secondary * ctx.blend_ratio)
                else:
                    voice_argument = ctx.voice

                # Send start message
                await websocket.send_json({
                    "type": "start",
                    "sample_rate": DEFAULT_SAMPLE_RATE,
                    "language": ctx.language,
                    "voice": ctx.voice,
                    "blend_with": ctx.blend_with,
                    "blend_ratio": ctx.blend_ratio,
                    "speed": ctx.speed
                })

                # Stream audio chunks
                header_sent = False
                async for samples, sample_rate in model.create_stream(
                    ctx.text,
                    voice=voice_argument,
                    speed=ctx.speed,
                    lang=ctx.language,
                ):
                    if not header_sent:
                        # Send WAV header
                        header = _build_wav_stream_header(sample_rate)
                        await websocket.send_bytes(header)
                        header_sent = True
                    
                    # Send PCM audio chunk
                    chunk = _audio_to_pcm16(samples)
                    if chunk:
                        await websocket.send_bytes(chunk)

                # Send end message
                await websocket.send_json({
                    "type": "end",
                    "message": "TTS synthesis completed"
                })

            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            except Exception as e:
                LOGGER.exception("Error during TTS synthesis")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Synthesis error: {str(e)}"
                })
                
    except WebSocketDisconnect:
        LOGGER.info("WebSocket connection closed by client")
    except Exception as e:
        LOGGER.exception("WebSocket connection error")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


@app.get("/healthz")
async def healthz() -> JSONResponse:
    try:
        model = await _load_model()
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Kokoro health check failed")
        raise HTTPException(status_code=503, detail=f"Model unavailable: {exc}") from exc
    payload = {
        "voices": len(model.get_voices()),
        "default_voice": DEFAULT_VOICE,
        "default_language": DEFAULT_LANGUAGE,
        "sample_rate": DEFAULT_SAMPLE_RATE,
    }
    return JSONResponse(payload)


@app.get("/api/voices")
async def list_voices() -> JSONResponse:
    model = await _load_model()
    return JSONResponse({"voices": model.get_voices()})


@app.post("/api/tts")
async def synthesize(request: TTSRequest) -> StreamingResponse:
    ctx = _resolve_synthesis_context(request)
    model = await _load_model()
    stream = _render_stream(model, ctx)

    headers = {
        "X-Sample-Rate": str(DEFAULT_SAMPLE_RATE),
        "X-Kokoro-Language": ctx.language,
        "X-Kokoro-Voice": ctx.voice,
    }
    if ctx.blend_with:
        headers["X-Kokoro-Blend-With"] = ctx.blend_with
        headers["X-Kokoro-Blend-Ratio"] = f"{ctx.blend_ratio:.2f}"

    if ctx.requested_sample_rate != DEFAULT_SAMPLE_RATE:
        LOGGER.warning(
            "Requested sample_rate=%s but Kokoro returns %s; continuing with native sample rate",
            ctx.requested_sample_rate,
            DEFAULT_SAMPLE_RATE,
        )

    return StreamingResponse(stream, media_type="audio/wav", headers=headers)


@app.websocket("/ws/tts")
async def websocket_tts(websocket: WebSocket):
    """WebSocket endpoint for seamless TTS streaming."""
    await handle_websocket_connection(websocket)


@app.websocket("/ws/tts/stream")
async def websocket_tts_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time streaming TTS (async.ai compatible)."""
    await handle_async_ai_compatible_streaming(websocket)


async def handle_async_ai_compatible_streaming(websocket: WebSocket):
    """Handle async.ai compatible WebSocket streaming protocol."""
    await websocket.accept()
    LOGGER.info("Async.ai compatible WebSocket connection established")
    
    try:
        # Load model if not already loaded
        model = await _load_model()
        
        # Wait for initialization message
        init_data = await websocket.receive_json()
        LOGGER.info("Received initialization: %s", init_data)
        
        # Parse initialization parameters
        voice_config = init_data.get("voice", {})
        voice_id = voice_config.get("id", DEFAULT_VOICE)
        model_id = init_data.get("model_id", "kokoro-v1.0")
        output_format = init_data.get("output_format", {})
        sample_rate = output_format.get("sample_rate", DEFAULT_SAMPLE_RATE)
        encoding = output_format.get("encoding", "pcm_s16le")
        container = output_format.get("container", "raw")
        
        # Validate parameters
        if encoding != "pcm_s16le":
            await websocket.send_json({
                "error": f"Unsupported encoding: {encoding}. Only pcm_s16le is supported"
            })
            return
        
        LOGGER.info("Initialized with voice=%s, sample_rate=%s", voice_id, sample_rate)
        
        # Buffer for accumulating text chunks
        text_buffer = []
        
        while True:
            # Wait for text chunks
            data = await websocket.receive_json()
            transcript = data.get("transcript", "")
            
            if transcript == "":
                # End of stream signal - process buffered text
                if text_buffer:
                    full_text = "".join(text_buffer).strip()
                    if full_text:
                        LOGGER.info("Processing final text: %s", full_text[:100] + "..." if len(full_text) > 100 else full_text)
                        
                        # Create synthesis context
                        ctx = WebSocketSynthesisContext(
                            text=full_text,
                            language=init_data.get("language", DEFAULT_LANGUAGE),
                            voice=voice_id,
                            blend_with=None,
                            blend_ratio=DEFAULT_BLEND_RATIO,
                            speed=init_data.get("speed", DEFAULT_SPEED),
                            requested_sample_rate=sample_rate
                        )
                        
                        # Stream audio chunks
                        async for samples, actual_sample_rate in model.create_stream(
                            ctx.text,
                            voice=ctx.voice,
                            speed=ctx.speed,
                            lang=ctx.language,
                        ):
                            # Convert to PCM16 and send as base64
                            pcm_data = _audio_to_pcm16(samples)
                            if pcm_data:
                                audio_b64 = base64.b64encode(pcm_data).decode('utf-8')
                                await websocket.send_json({
                                    "audio": audio_b64,
                                    "final": False
                                })
                        
                        # Send final message
                        await websocket.send_json({
                            "audio": "",
                            "final": True
                        })
                    
                    text_buffer.clear()
                break
            else:
                # Accumulate text chunks
                text_buffer.append(transcript)
                LOGGER.debug("Buffered text chunk: %s", transcript)
                
    except WebSocketDisconnect:
        LOGGER.info("Async.ai compatible WebSocket connection closed by client")
    except Exception as e:
        LOGGER.exception("Async.ai compatible WebSocket error")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


async def handle_live_streaming_connection(websocket: WebSocket):
    """Handle true live streaming WebSocket connection for Kokoro TTS."""
    await websocket.accept()
    LOGGER.info("Live streaming WebSocket connection established")
    
    try:
        # Load model if not already loaded
        model = await _load_model()
        
        # Wait for initialization
        init_data = await websocket.receive_json()
        voice_id = init_data.get("voice", DEFAULT_VOICE)
        language = init_data.get("language", DEFAULT_LANGUAGE)
        speed = init_data.get("speed", DEFAULT_SPEED)
        
        LOGGER.info("Live streaming initialized: voice=%s, language=%s, speed=%s",
                   voice_id, language, speed)
        
        # Send ready signal
        await websocket.send_json({
            "type": "ready",
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "format": "pcm_s16le"
        })
        
        # Process text chunks incrementally
        chunk_count = 0
        while True:
            # Receive text chunk
            data = await websocket.receive_text()
            
            if data == "":
                # End of stream signal
                LOGGER.info("Live streaming completed: %d chunks processed", chunk_count)
                await websocket.send_json({
                    "type": "end",
                    "total_chunks": chunk_count
                })
                break
            
            # Process text chunk immediately
            LOGGER.info("Processing live text chunk: '%s'", data[:50] + "..." if len(data) > 50 else data)
            
            try:
                # Create synthesis context for this chunk
                ctx = WebSocketSynthesisContext(
                    text=data,
                    language=language,
                    voice=voice_id,
                    blend_with=None,
                    blend_ratio=DEFAULT_BLEND_RATIO,
                    speed=speed,
                    requested_sample_rate=DEFAULT_SAMPLE_RATE
                )
                
                # Prepare voice argument
                voice_argument: str | np.ndarray = ctx.voice
                
                # Stream audio for this chunk immediately
                header_sent = False
                async for samples, sample_rate in model.create_stream(
                    ctx.text,
                    voice=voice_argument,
                    speed=ctx.speed,
                    lang=ctx.language,
                ):
                    if not header_sent:
                        # Send WAV header for this chunk
                        header = _build_wav_stream_header(sample_rate)
                        await websocket.send_bytes(header)
                        header_sent = True
                    
                    # Send PCM audio chunk
                    chunk = _audio_to_pcm16(samples)
                    if chunk:
                        chunk_count += 1
                        # Send binary audio data directly (no control message)
                        await websocket.send_bytes(chunk)
                
            except Exception as e:
                LOGGER.exception("Error during live streaming synthesis")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Synthesis error: {str(e)}"
                })
                break
                
    except WebSocketDisconnect:
        LOGGER.info("Live streaming WebSocket connection closed by client")
    except Exception as e:
        LOGGER.exception("Live streaming WebSocket error")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


@app.websocket("/ws/tts/live")
async def websocket_tts_live(websocket: WebSocket):
    """True live streaming WebSocket endpoint for Kokoro TTS."""
    await handle_live_streaming_connection(websocket)


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("KOKORO_REST_PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
