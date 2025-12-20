'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { liveKitClient } from '@/lib/livekit-client';
import { RemoteParticipant } from 'livekit-client';
import { useTelemetry, TurnState } from './use-telemetry';

export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed';

export type Message = {
  id: string;
  speaker: 'user' | 'agent';
  text: string;
  isFinal: boolean;
  timestamp: number;
};

export interface UseLiveKitReturn {
  isConnected: boolean;
  connectionState: ConnectionState;
  agentParticipant: RemoteParticipant | null;
  audioStream: MediaStream | null;
  localAudioStream: MediaStream | null;
  error: string | null;
  transcription: string;
  response: string;
  messages: Message[];
  vadState: { energy: number; state: 'speaking' | 'silence' };
  llmState: boolean;
  ttsState: boolean;
  metrics: { tokens: number; audioChunks: number; latency?: number };
  turnState: TurnState;
  ragLoading: boolean;
  ragLoadingMessage: string;
  connect: (agentId: string, options?: { deviceId?: string }) => Promise<void>;
  disconnect: () => Promise<void>;
  switchMicrophone: (deviceId?: string) => Promise<void>;
}

export function useLiveKit(): UseLiveKitReturn {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('disconnected');
  const [agentParticipant, setAgentParticipant] =
    useState<RemoteParticipant | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);
  const [localAudioStream, setLocalAudioStream] = useState<MediaStream | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [transcription, setTranscription] = useState<string>('');
  const [response, setResponse] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [vadState, setVadState] = useState<{
    energy: number;
    state: 'speaking' | 'silence';
  }>({ energy: 0, state: 'silence' });

  // Indicator states
  const [llmState, setLlmState] = useState<boolean>(false);
  const [ttsState, setTtsState] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<{
    tokens: number;
    audioChunks: number;
    latency?: number;
  }>({ tokens: 0, audioChunks: 0 });

  // RAG loading state
  const [ragLoading, setRagLoading] = useState<boolean>(false);
  const [ragLoadingMessage, setRagLoadingMessage] = useState<string>('');

  // Telemetry hook
  const { turnState, updateTelemetry, resetTelemetry } = useTelemetry();

  // Latency tracking
  const lastSpeechEnd = useRef<number>(0);

  // Refs for tracking ongoing messages
  const lastAgentMessageId = useRef<string | null>(null);
  const lastUserMessageId = useRef<string | null>(null);

  // Ref to track if we're mounted to avoid state updates on unmount
  const isMounted = useRef(true);

  // Helper to generate unique IDs for messages
  const generateId = useCallback(() => crypto.randomUUID(), []);

  const handleTranscriptUpdate = useCallback(
    (data: any) => {
      const isFinal = data.is_final;
      const text = data.text;

      if (isFinal) {
        setTranscription((prev) => prev + ' ' + text);
        setMessages((prev) => {
          const index = prev.findIndex(
            (m) => m.id === lastUserMessageId.current
          );
          if (index >= 0 && !prev[index].isFinal) {
            const updated = [...prev];
            updated[index] = {
              ...updated[index],
              text: text.trim(),
              isFinal: true,
            };
            return updated;
          }
          const id = generateId();
          lastUserMessageId.current = id;
          return [
            ...prev,
            {
              id,
              speaker: 'user',
              text: text.trim(),
              isFinal: true,
              timestamp: Date.now(),
            },
          ];
        });
      } else {
        setMessages((prev) => {
          const index = prev.findIndex(
            (m) => m.id === lastUserMessageId.current
          );
          if (index >= 0 && !prev[index].isFinal) {
            const updated = [...prev];
            updated[index] = {
              ...updated[index],
              text: text.trim(),
              isFinal: false,
            };
            return updated;
          }
          const id = generateId();
          lastUserMessageId.current = id;
          return [
            ...prev,
            {
              id,
              speaker: 'user',
              text: text.trim(),
              isFinal: false,
              timestamp: Date.now(),
            },
          ];
        });
      }
    },
    [generateId]
  );

  const handleAssistantResponse = useCallback(
    (data: any) => {
      if (data.text) {
        setResponse((prev) => prev + data.text);
        setMessages((prev) => {
          const index = prev.findIndex(
            (m) => m.id === lastAgentMessageId.current
          );
          if (index >= 0) {
            const updated = [...prev];
            updated[index] = {
              ...updated[index],
              text: updated[index].text + data.text,
              isFinal: false,
            };
            return updated;
          }
          const id = generateId();
          lastAgentMessageId.current = id;
          return [
            ...prev,
            {
              id,
              speaker: 'agent',
              text: data.text,
              isFinal: false,
              timestamp: Date.now(),
            },
          ];
        });
      }
      if (data.is_complete) {
        setResponse((prev) => prev + '\n\n');
        setLlmState(false);
        setMessages((prev) => {
          const index = prev.findIndex(
            (m) => m.id === lastAgentMessageId.current
          );
          if (index >= 0) {
            const updated = [...prev];
            updated[index] = { ...updated[index], isFinal: true };
            return updated;
          }
          return prev;
        });
      }
    },
    [generateId]
  );

  useEffect(() => {
    isMounted.current = true;

    liveKitClient.onConnectionStateChange = (state: string) => {
      if (isMounted.current) setConnectionState(state as ConnectionState);
    };

    liveKitClient.onAgentJoined = (p: RemoteParticipant) => {
      if (isMounted.current) setAgentParticipant(p);
    };

    liveKitClient.onAgentLeft = () => {
      if (isMounted.current) {
        setAgentParticipant(null);
        setAudioStream(null);
      }
    };

    liveKitClient.onAudioTrack = (s: MediaStream) => {
      if (isMounted.current) setAudioStream(s);
    };

    liveKitClient.onLocalAudioTrack = (s: MediaStream) => {
      if (isMounted.current) setLocalAudioStream(s);
    };

    liveKitClient.onError = (err: string) => {
      if (isMounted.current) {
        setError(err);
        if (connectionState === 'connecting') setConnectionState('failed');
      }
    };

    liveKitClient.onDataReceived = (payload: Uint8Array) => {
      if (!isMounted.current) return;
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        switch (data.type) {
          case 'transcript_update':
            handleTranscriptUpdate(data);
            break;
          case 'assistant_response':
            handleAssistantResponse(data);
            break;
          case 'vad_update':
            setVadState({ energy: data.energy, state: data.state });
            if (data.telemetry) updateTelemetry(data.telemetry);
            break;
          case 'speech_start':
            setVadState((prev) => ({ ...prev, state: 'speaking' }));
            resetTelemetry();
            updateTelemetry({ vad_speech_detected: true });
            break;
          case 'speech_end':
            setVadState((prev) => ({ ...prev, state: 'silence' }));
            lastSpeechEnd.current = Date.now();
            updateTelemetry({ vad_end_of_speech_detected: true });
            break;
          case 'bot_responding_start':
            setResponse('');
            setLlmState(true);
            {
              const id = generateId();
              lastAgentMessageId.current = id;
              setMessages((prev) => [
                ...prev,
                {
                  id,
                  speaker: 'agent',
                  text: '',
                  isFinal: false,
                  timestamp: Date.now(),
                },
              ]);
            }
            break;
          case 'bot_responding_end':
            setLlmState(false);
            setTtsState(false);
            break;
          case 'audio_chunk':
            {
              const now = Date.now();
              const latency =
                lastSpeechEnd.current > 0
                  ? now - lastSpeechEnd.current
                  : undefined;
              if (latency !== undefined) lastSpeechEnd.current = 0;
              setMetrics((prev) => ({
                ...prev,
                audioChunks: prev.audioChunks + 1,
                latency: latency !== undefined ? latency : prev.latency,
              }));
              setTtsState(true);
            }
            break;
          case 'telemetry_update':
            if (data.data) updateTelemetry(data.data);
            break;
          case 'rag_loading_start':
            setRagLoading(true);
            setRagLoadingMessage(data.message || 'Initialisation...');
            break;
          case 'rag_loading_complete':
          case 'rag_loading_error':
            setRagLoading(false);
            setRagLoadingMessage('');
            break;
        }
      } catch (e) {
        console.error('Data error:', e);
      }
    };
  }, [
    connectionState,
    handleTranscriptUpdate,
    handleAssistantResponse,
    generateId,
    updateTelemetry,
    resetTelemetry,
  ]);

  useEffect(() => {
    isMounted.current = true;

    // Check initial state
    if (liveKitClient.isConnected()) {
      setConnectionState('connected');
      setAgentParticipant(liveKitClient.getAgentParticipant());
    }

    return () => {
      isMounted.current = false;
      // We don't disconnect here to allow persistent connections across navigation if desired,
      // but for this specific component it might be better to handle cleanup in the component itself.
    };
  }, [connectionState]);

  const connect = useCallback(
    async (agentId: string, options?: { deviceId?: string }) => {
      try {
        setError(null);
        setConnectionState('connecting');
        await liveKitClient.connect(agentId, options);
        // State updates will be handled by event listeners
      } catch (err) {
        if (isMounted.current) {
          const message =
            err instanceof Error ? err.message : 'Connection failed';
          setError(message);
          setConnectionState('failed');
        }
      }
    },
    []
  );

  const disconnect = useCallback(async () => {
    try {
      await liveKitClient.disconnect();
      if (isMounted.current) {
        setConnectionState('disconnected');
        setAgentParticipant(null);
        setAudioStream(null);
        setLocalAudioStream(null);
      }
    } catch (err) {
      console.error('Disconnect failed:', err);
    }
  }, []);

  const switchMicrophone = useCallback(async (deviceId?: string) => {
    try {
      await liveKitClient.switchMicrophone(deviceId);
      // The local audio stream will be updated via onLocalAudioTrack event
    } catch (err) {
      if (isMounted.current) {
        const message =
          err instanceof Error ? err.message : 'Failed to switch microphone';
        setError(message);
      }
      throw err;
    }
  }, []);

  return {
    isConnected: connectionState === 'connected',
    connectionState,
    agentParticipant,
    audioStream,
    localAudioStream,
    error,
    transcription,
    response,
    messages,
    vadState,
    llmState,
    ttsState,
    metrics,
    turnState,
    ragLoading,
    ragLoadingMessage,
    connect,
    disconnect,
    switchMicrophone,
  };
}
