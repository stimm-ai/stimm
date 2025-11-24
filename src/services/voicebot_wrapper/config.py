"""
Voicebot wrapper specific configuration.

This config only contains settings specific to the voicebot wrapper.
Individual service configurations (STT, TTS, RAG) are managed by their own configs.
"""

import os
from typing import Optional

class VoicebotConfig:
    """Voicebot wrapper specific configuration settings."""

    # Voice Activity Detection (VAD) settings
    VAD_THRESHOLD: float = float(os.getenv("VOICEBOT_VAD_THRESHOLD", "0.01"))
    SILENCE_TIMEOUT_MS: int = int(os.getenv("VOICEBOT_SILENCE_TIMEOUT_MS", "1000"))
    MIN_SPEECH_DURATION_MS: int = int(os.getenv("VOICEBOT_MIN_SPEECH_DURATION_MS", "300"))

    # WebRTC VAD settings (for backend VAD processing)
    WEBRTC_VAD_AGGRESSIVENESS: int = int(os.getenv("VOICEBOT_WEBRTC_VAD_AGGRESSIVENESS", "2"))
    WEBRTC_VAD_FRAME_DURATION_MS: int = int(os.getenv("VOICEBOT_WEBRTC_VAD_FRAME_DURATION_MS", "30"))
    WEBRTC_VAD_SAMPLE_RATE: int = 16000  # WebRTC VAD requires 16kHz
    WEBRTC_VAD_VOICE_START_FRAMES: int = 2  # Consecutive voice frames to start voice activity
    WEBRTC_VAD_VOICE_END_FRAMES: int = 6   # Consecutive silence frames to end voice activity

    # Audio processing settings (for WebSocket communication)
    SAMPLE_RATE: int = int(os.getenv("VOICEBOT_SAMPLE_RATE", "16000"))
    CHUNK_SIZE_MS: int = int(os.getenv("VOICEBOT_CHUNK_SIZE_MS", "20"))
    CHANNELS: int = 1  # Mono audio





    # TTS Interface text for simulation
    TTS_INTERFACE_TEXT: str = os.getenv("TTS_INTERFACE_TEXT", "Cette démonstration met en avant la diffusion en temps réel des jetons d'un modèle de langage. Merci d'avoir écouté ce texte. Ce test permer, grâce à des sliders de visualisation, de vérifier si la réception de chunks auidio se fait bien en parrallèlle avec l'envoie des tokens issue du LLM. J'éspère que cela vous aidera. A bientôt pour de nouvelles aventures. Et surtout prenez soin de vous. Au revoir.")

    # TTS Buffering configuration
    PRE_TTS_BUFFERING_LEVEL: str = os.getenv("PRE_TTS_BUFFERING_LEVEL", "LOW")

    @property
    def chunk_size_samples(self) -> int:
        """Calculate the number of samples per audio chunk."""
        return int((self.SAMPLE_RATE / 1000) * self.CHUNK_SIZE_MS)

    @property
    def frame_size(self) -> int:
        """Alias for chunk_size_samples for compatibility."""
        return self.chunk_size_samples

    @property
    def bytes_per_chunk(self) -> int:
        """Calculate the size of each audio chunk in bytes."""
        return self.chunk_size_samples * 2  # 2 bytes per sample for 16-bit PCM

    @property
    def webrtc_vad_frame_size(self) -> int:
        """Calculate WebRTC VAD frame size in samples."""
        return int((self.WEBRTC_VAD_SAMPLE_RATE / 1000) * self.WEBRTC_VAD_FRAME_DURATION_MS)

    @property
    def webrtc_vad_bytes_per_frame(self) -> int:
        """Calculate WebRTC VAD frame size in bytes."""
        return self.webrtc_vad_frame_size * 2  # 2 bytes per sample for 16-bit PCM

# Global configuration instance
voicebot_config = VoicebotConfig()