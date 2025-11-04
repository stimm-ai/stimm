"""
STT Configuration Module
"""

import os
from dotenv import load_dotenv

load_dotenv()

class STTConfig:
    """Configuration for Speech-to-Text providers"""

    def __init__(self):
        self.provider = os.getenv("STT_PROVIDER", "whisper.local")
        self.whisper_local_url = os.getenv("WHISPER_LOCAL_STT_URL", "ws://whisper-stt:8003")
        self.whisper_local_path = os.getenv("WHISPER_STT_WS_PATH", "/api/stt/stream")
        self.whisper_local_full_url = f"{self.whisper_local_url}{self.whisper_local_path}"
        
        # Deepgram configuration
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.deepgram_model = os.getenv("DEEPGRAM_MODEL", "nova-2")
        self.deepgram_language = os.getenv("DEEPGRAM_LANGUAGE", "fr")

    def get_provider(self):
        """Get the current STT provider"""
        return self.provider

    def get_whisper_local_config(self):
        """Get whisper.local specific configuration"""
        return {
            "url": self.whisper_local_url,
            "path": self.whisper_local_path,
            "full_url": self.whisper_local_full_url
        }

    def get_deepgram_config(self):
        """Get deepgram.com specific configuration"""
        return {
            "api_key": self.deepgram_api_key,
            "model": self.deepgram_model,
            "language": self.deepgram_language
        }

# Initialize the configuration
stt_config = STTConfig()