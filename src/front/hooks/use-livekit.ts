'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { liveKitClient } from '@/lib/livekit-client'
import { RemoteParticipant } from 'livekit-client'
import { useTelemetry, TurnState } from './use-telemetry'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed'

export interface UseLiveKitReturn {
  isConnected: boolean
  connectionState: ConnectionState
  agentParticipant: RemoteParticipant | null
  audioStream: MediaStream | null
  error: string | null
  transcription: string
  response: string
  vadState: { energy: number, state: 'speaking' | 'silence' }
  llmState: boolean
  ttsState: boolean
  metrics: { tokens: number, audioChunks: number, latency?: number }
  turnState: TurnState
  connect: (agentId: string) => Promise<void>
  disconnect: () => Promise<void>
}

export function useLiveKit(): UseLiveKitReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [agentParticipant, setAgentParticipant] = useState<RemoteParticipant | null>(null)
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  // Data states
  const [transcription, setTranscription] = useState<string>('')
  const [response, setResponse] = useState<string>('')
  const [vadState, setVadState] = useState<{ energy: number, state: 'speaking' | 'silence' }>({ energy: 0, state: 'silence' })
  
  // Indicator states
  const [llmState, setLlmState] = useState<boolean>(false)
  const [ttsState, setTtsState] = useState<boolean>(false)
  const [metrics, setMetrics] = useState<{ tokens: number, audioChunks: number, latency?: number }>({ tokens: 0, audioChunks: 0 })

  // Telemetry hook
  const { turnState, updateTelemetry, resetTelemetry } = useTelemetry()

  // Latency tracking
  const lastSpeechEnd = useRef<number>(0)

  // Ref to track if we're mounted to avoid state updates on unmount
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    
    // Set up event listeners
    liveKitClient.onConnectionStateChange = (state: string) => {
      if (isMounted.current) {
        setConnectionState(state as ConnectionState)
      }
    }

    liveKitClient.onAgentJoined = (participant: RemoteParticipant) => {
      if (isMounted.current) {
        setAgentParticipant(participant)
      }
    }

    liveKitClient.onAgentLeft = () => {
      if (isMounted.current) {
        setAgentParticipant(null)
        setAudioStream(null)
      }
    }

    liveKitClient.onAudioTrack = (stream: MediaStream) => {
      if (isMounted.current) {
        setAudioStream(stream)
      }
    }

    liveKitClient.onError = (err: string) => {
      if (isMounted.current) {
        setError(err)
        // If error occurs during connection, reset state
        if (connectionState === 'connecting') {
          setConnectionState('failed')
        }
      }
    }

    liveKitClient.onDataReceived = (payload: Uint8Array, participant?: RemoteParticipant) => {
      if (!isMounted.current) return
      
      try {
        const text = new TextDecoder().decode(payload)
        const data = JSON.parse(text)
        
        console.log('📦 Hook Data:', data)
        
        switch (data.type) {
          case 'transcript_update':
            // Append or replace? Usually STT sends partials then final.
            // Simplified: just show latest text for now, or append if final.
            if (data.is_final) {
               setTranscription(prev => prev + ' ' + data.text)
            } else {
               // For partials, we might want a separate "current utterance" state
               // But here we'll just show it.
               // To avoid flickering, maybe just log or have a separate UI element.
               // Let's just update transcription for now.
               // setTranscription(data.text)
            }
            break
            
          case 'assistant_response':
            if (data.text) {
              setResponse(prev => prev + data.text)
            }
            if (data.is_complete) {
               setResponse(prev => prev + '\n\n')
               setLlmState(false)
            }
            break
            
          case 'vad_update':
            setVadState({ energy: data.energy, state: data.state })
            if (data.telemetry) {
              updateTelemetry(data.telemetry)
            }
            break
            
          case 'speech_start':
            setVadState(prev => ({ ...prev, state: 'speaking' }))
            resetTelemetry() // Reset telemetry on new speech start
            updateTelemetry({ vad_speech_detected: true })
            break
            
          case 'speech_end':
            setVadState(prev => ({ ...prev, state: 'silence' }))
            lastSpeechEnd.current = Date.now()
            updateTelemetry({ vad_end_of_speech_detected: true })
            break
            
          case 'bot_responding_start':
             // Maybe clear response if it's a new turn?
             setResponse('')
             setLlmState(true)
             break
             
          case 'bot_responding_end':
             setLlmState(false)
             setTtsState(false) // Assuming TTS ends shortly after or we track chunks
             break
             
          case 'audio_chunk':
             // Calculate latency if this is the first chunk after speech end
             let currentLatency: number | undefined;
             if (lastSpeechEnd.current > 0) {
                currentLatency = Date.now() - lastSpeechEnd.current;
                lastSpeechEnd.current = 0; // Reset so we don't calculate for subsequent chunks
             }

             setMetrics(prev => ({
               ...prev,
               audioChunks: prev.audioChunks + 1,
               latency: currentLatency !== undefined ? currentLatency : prev.latency
             }))
             setTtsState(true)
             break

          case 'telemetry_update':
             if (data.data) {
               updateTelemetry(data.data)
             }
             break
         }
      } catch (e) {
        console.error('Failed to parse data packet:', e)
      }
    }

    // Check initial state
    if (liveKitClient.isConnected()) {
      setConnectionState('connected')
      setAgentParticipant(liveKitClient.getAgentParticipant())
    }

    return () => {
      isMounted.current = false
      // We don't disconnect here to allow persistent connections across navigation if desired,
      // but for this specific component it might be better to handle cleanup in the component itself.
    }
  }, [connectionState])

  const connect = useCallback(async (agentId: string) => {
    try {
      setError(null)
      setConnectionState('connecting')
      await liveKitClient.connect(agentId)
      // State updates will be handled by event listeners
    } catch (err) {
      if (isMounted.current) {
        const message = err instanceof Error ? err.message : 'Connection failed'
        setError(message)
        setConnectionState('failed')
      }
    }
  }, [])

  const disconnect = useCallback(async () => {
    try {
      await liveKitClient.disconnect()
      if (isMounted.current) {
        setConnectionState('disconnected')
        setAgentParticipant(null)
        setAudioStream(null)
      }
    } catch (err) {
      console.error('Disconnect failed:', err)
    }
  }, [])

  return {
    isConnected: connectionState === 'connected',
    connectionState,
    agentParticipant,
    audioStream,
    error,
    transcription,
    response,
    vadState,
    llmState,
    ttsState,
    metrics,
    turnState,
    connect,
    disconnect
  }
}