from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class VADState(str, Enum):
    SPEAKING = "speaking"
    SILENCE = "silence"


@dataclass
class TurnState:
    """
    Holds the boolean flags and real-time data for the current conversation turn.
    These flags automatically reset at the beginning of a new turn (when VAD_SPEECH_DETECTED becomes True).
    """

    # Boolean Flags
    vad_speech_detected: bool = False
    vad_end_of_speech_detected: bool = False
    stt_streaming_started: bool = False
    stt_streaming_ended: bool = False
    llm_streaming_started: bool = False
    llm_streaming_ended: bool = False
    tts_streaming_started: bool = False
    tts_streaming_ended: bool = False
    webrtc_streaming_agent_audio_response_started: bool = False
    webrtc_streaming_agent_audio_response_ended: bool = False

    # Timestamps & Real-Time Data
    vad_end_of_speech_detected_time: Optional[float] = None
    webrtc_streaming_agent_audio_response_started_time: Optional[float] = None
    vad_energy: float = 0.0
    vad_state: VADState = VADState.SILENCE

    # Computed Metrics
    agent_response_delay: Optional[float] = None

    def reset(self):
        """Reset all flags and metrics for a new turn."""
        self.vad_speech_detected = False
        self.vad_end_of_speech_detected = False
        self.stt_streaming_started = False
        self.stt_streaming_ended = False
        self.llm_streaming_started = False
        self.llm_streaming_ended = False
        self.tts_streaming_started = False
        self.tts_streaming_ended = False
        self.webrtc_streaming_agent_audio_response_started = False
        self.webrtc_streaming_agent_audio_response_ended = False

        self.vad_end_of_speech_detected_time = None
        self.webrtc_streaming_agent_audio_response_started_time = None
        # Note: We don't reset vad_energy or vad_state as they are continuous

        self.agent_response_delay = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return asdict(self)

    def calculate_metrics(self):
        """Calculate derived metrics based on timestamps."""
        if self.webrtc_streaming_agent_audio_response_started_time is not None and self.vad_end_of_speech_detected_time is not None:
            self.agent_response_delay = self.webrtc_streaming_agent_audio_response_started_time - self.vad_end_of_speech_detected_time
