"""
TTS Configuration Module
"""

import os
import tempfile
import uuid

# Configuration pour l'enregistrement des chunks audio
TTS_RECORD_CHUNKS = os.getenv('TTS_RECORD_CHUNKS', 'false').lower() == 'true'
TTS_CHUNKS_DIR = os.getenv('TTS_CHUNKS_DIR', '/tmp/tts_chunks_web')
from dotenv import load_dotenv

load_dotenv()

class TTSConfig:
    """Configuration for Text-to-Speech providers"""

    def __init__(self):
        self.provider = os.getenv("TTS_PROVIDER", "async.ai")
        # Async.ai specific configuration
        self.async_ai_url = os.getenv("ASYNC_AI_TTS_URL",
                                   "wss://api.async.ai/text_to_speech/websocket/ws")
        self.async_ai_api_key = os.getenv("ASYNC_API_KEY")
        self.async_ai_voice_id = os.getenv("ASYNC_AI_TTS_VOICE_ID",
                                         "e7b694f8-d277-47ff-82bf-cb48e7662647")
        self.async_ai_model_id = os.getenv("ASYNC_AI_TTS_MODEL_ID", "asyncflow_v2.0")
        self.async_ai_sample_rate = int(os.getenv("ASYNC_AI_TTS_SAMPLE_RATE", "44100"))
        self.async_ai_encoding = os.getenv("ASYNC_AI_TTS_ENCODING", "pcm_s16le")
        self.async_ai_container = os.getenv("ASYNC_AI_TTS_CONTAINER", "raw")
        
        # Kokoro.local specific configuration
        self.kokoro_local_url = os.getenv("KOKORO_LOCAL_TTS_URL",
                                       "ws://kokoro-tts:5000/ws/tts/stream")
        self.kokoro_local_voice_id = os.getenv("KOKORO_TTS_DEFAULT_VOICE", "af_sarah")
        self.kokoro_local_sample_rate = int(os.getenv("KOKORO_TTS_SAMPLE_RATE", "44100"))
        self.kokoro_local_encoding = os.getenv("KOKORO_TTS_ENCODING", "pcm_s16le")
        self.kokoro_local_container = os.getenv("KOKORO_TTS_CONTAINER", "raw")
        self.kokoro_local_language = os.getenv("KOKORO_TTS_DEFAULT_LANGUAGE", "fr-fr")
        self.kokoro_local_speed = float(os.getenv("KOKORO_TTS_DEFAULT_SPEED", "0.8"))

        # Deepgram specific configuration
        self.deepgram_tts_api_key = os.getenv("DEEPGRAM_TTS_API_KEY")
        self.deepgram_model = os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en")
        self.deepgram_sample_rate = int(os.getenv("DEEPGRAM_TTS_SAMPLE_RATE", "16000"))
        self.deepgram_encoding = os.getenv("DEEPGRAM_TTS_ENCODING", "linear16")
        
        # ElevenLabs specific configuration
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_TTS_API_KEY")
        self.elevenlabs_voice_id = os.getenv("ELEVENLABS_TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.elevenlabs_model_id = os.getenv("ELEVENLABS_TTS_MODEL_ID", "eleven_flash_v2_5")
        self.elevenlabs_sample_rate = int(os.getenv("ELEVENLABS_TTS_SAMPLE_RATE", "22050"))
        self.elevenlabs_encoding = os.getenv("ELEVENLABS_TTS_ENCODING", "mp3")
        self.elevenlabs_output_format = os.getenv("ELEVENLABS_TTS_OUTPUT_FORMAT", "mp3_22050_32")

    def get_provider(self):
        """Get the current TTS provider"""
        return self.provider

# Initialize the configuration
tts_config = TTSConfig()