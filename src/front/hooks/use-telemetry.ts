import { useState } from 'react';

export interface TurnState {
  vad_speech_detected: boolean;
  vad_end_of_speech_detected: boolean;
  stt_streaming_started: boolean;
  stt_streaming_ended: boolean;
  llm_streaming_started: boolean;
  llm_streaming_ended: boolean;
  tts_streaming_started: boolean;
  tts_streaming_ended: boolean;
  webrtc_streaming_agent_audio_response_started: boolean;
  webrtc_streaming_agent_audio_response_ended: boolean;

  vad_end_of_speech_detected_time: number | null;
  webrtc_streaming_agent_audio_response_started_time: number | null;
  vad_energy: number;
  vad_state: 'speaking' | 'silence';

  agent_response_delay: number | null;
}

export const initialTurnState: TurnState = {
  vad_speech_detected: false,
  vad_end_of_speech_detected: false,
  stt_streaming_started: false,
  stt_streaming_ended: false,
  llm_streaming_started: false,
  llm_streaming_ended: false,
  tts_streaming_started: false,
  tts_streaming_ended: false,
  webrtc_streaming_agent_audio_response_started: false,
  webrtc_streaming_agent_audio_response_ended: false,

  vad_end_of_speech_detected_time: null,
  webrtc_streaming_agent_audio_response_started_time: null,
  vad_energy: 0,
  vad_state: 'silence',

  agent_response_delay: null,
};

export interface TelemetryHook {
  turnState: TurnState;
  updateTelemetry: (data: Partial<TurnState>) => void;
  resetTelemetry: () => void;
}

export function useTelemetry(): TelemetryHook {
  const [turnState, setTurnState] = useState<TurnState>(initialTurnState);

  const updateTelemetry = (data: Partial<TurnState>) => {
    setTurnState((prev) => ({
      ...prev,
      ...data,
    }));
  };

  const resetTelemetry = () => {
    setTurnState(initialTurnState);
  };

  return {
    turnState,
    updateTelemetry,
    resetTelemetry,
  };
}
