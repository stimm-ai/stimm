'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { liveKitClient } from '@/lib/livekit-client'
import { RemoteParticipant } from 'livekit-client'
import { useTelemetry, TurnState } from './use-telemetry'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed'

export type Message = {
  id: string
  speaker: 'user' | 'agent'
  text: string
  isFinal: boolean
  timestamp: number
}

export interface UseLiveKitReturn {
  isConnected: boolean
  connectionState: ConnectionState
  agentParticipant: RemoteParticipant | null
  audioStream: MediaStream | null
  localAudioStream: MediaStream | null
  error: string | null
  transcription: string
  response: string
  messages: Message[]
  vadState: { energy: number, state: 'speaking' | 'silence' }
  llmState: boolean
  ttsState: boolean
  metrics: { tokens: number, audioChunks: number, latency?: number }
  turnState: TurnState
  ragLoading: boolean
  ragLoadingMessage: string
  connect: (agentId: string, options?: { deviceId?: string }) => Promise<void>
  disconnect: () => Promise<void>
  switchMicrophone: (deviceId?: string) => Promise<void>
}

export function useLiveKit(): UseLiveKitReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [agentParticipant, setAgentParticipant] = useState<RemoteParticipant | null>(null)
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null)
  const [localAudioStream, setLocalAudioStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Data states
  const [transcription, setTranscription] = useState<string>('')
  const [response, setResponse] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [vadState, setVadState] = useState<{ energy: number, state: 'speaking' | 'silence' }>({ energy: 0, state: 'silence' })

  // Indicator states
  const [llmState, setLlmState] = useState<boolean>(false)
  const [ttsState, setTtsState] = useState<boolean>(false)
  const [metrics, setMetrics] = useState<{ tokens: number, audioChunks: number, latency?: number }>({ tokens: 0, audioChunks: 0 })

  // RAG loading state
  const [ragLoading, setRagLoading] = useState<boolean>(false)
  const [ragLoadingMessage, setRagLoadingMessage] = useState<string>('')

  // Telemetry hook
  const { turnState, updateTelemetry, resetTelemetry } = useTelemetry()

  // Latency tracking
  const lastSpeechEnd = useRef<number>(0)

  // Refs for tracking ongoing messages
  const lastAgentMessageId = useRef<string | null>(null)
  const lastUserMessageId = useRef<string | null>(null)

  // Ref to track if we're mounted to avoid state updates on unmount
  const isMounted = useRef(true)

  // Helper to generate unique IDs for messages
  const generateId = () => Date.now().toString(36) + Math.random().toString(36).substring(2)

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

    liveKitClient.onLocalAudioTrack = (stream: MediaStream) => {
      if (isMounted.current) {
        setLocalAudioStream(stream)
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

        //console.log('📦 Hook Data:', data)

        switch (data.type) {
          case 'transcript_update':
            if (data.is_final) {
              // Final transcript
              setTranscription(prev => prev + ' ' + data.text)
              setMessages(prev => {
                const lastIndex = prev.findIndex(m => m.id === lastUserMessageId.current)
                if (lastIndex >= 0 && !prev[lastIndex].isFinal) {
                  // Update existing non-final user message
                  const updated = [...prev]
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    text: data.text.trim(),
                    isFinal: true
                  }
                  return updated
                } else {
                  // Create new final user message
                  const id = generateId()
                  lastUserMessageId.current = id
                  const newMessage: Message = {
                    id,
                    speaker: 'user',
                    text: data.text.trim(),
                    isFinal: true,
                    timestamp: Date.now()
                  }
                  return [...prev, newMessage]
                }
              })
            } else {
              // Partial transcript
              setMessages(prev => {
                const lastIndex = prev.findIndex(m => m.id === lastUserMessageId.current)
                if (lastIndex >= 0 && !prev[lastIndex].isFinal) {
                  // Update existing non-final user message
                  const updated = [...prev]
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    text: data.text.trim(),
                    isFinal: false
                  }
                  return updated
                } else {
                  // Create new non-final user message
                  const id = generateId()
                  lastUserMessageId.current = id
                  const newMessage: Message = {
                    id,
                    speaker: 'user',
                    text: data.text.trim(),
                    isFinal: false,
                    timestamp: Date.now()
                  }
                  return [...prev, newMessage]
                }
              })
            }
            break

          case 'assistant_response':
            if (data.text) {
              setResponse(prev => prev + data.text)
              setMessages(prev => {
                const lastIndex = prev.findIndex(m => m.id === lastAgentMessageId.current)
                if (lastIndex >= 0) {
                  // Update existing message
                  const updated = [...prev]
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    text: updated[lastIndex].text + data.text,
                    isFinal: false
                  }
                  return updated
                } else {
                  // Create new agent message
                  const id = generateId()
                  lastAgentMessageId.current = id
                  const newMessage: Message = {
                    id,
                    speaker: 'agent',
                    text: data.text,
                    isFinal: false,
                    timestamp: Date.now()
                  }
                  return [...prev, newMessage]
                }
              })
            }
            if (data.is_complete) {
              setResponse(prev => prev + '\n\n')
              setLlmState(false)
              // Mark the last agent message as final
              setMessages(prev => {
                const lastIndex = prev.findIndex(m => m.id === lastAgentMessageId.current)
                if (lastIndex >= 0) {
                  const updated = [...prev]
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    isFinal: true
                  }
                  return updated
                }
                return prev
              })
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
            // Clear response for new turn
            setResponse('')
            setLlmState(true)
            // Create a new agent message placeholder
            const id = generateId()
            lastAgentMessageId.current = id
            const newMessage: Message = {
              id,
              speaker: 'agent',
              text: '',
              isFinal: false,
              timestamp: Date.now()
            }
            setMessages(prev => [...prev, newMessage])
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

          case 'rag_loading_start':
            setRagLoading(true)
            setRagLoadingMessage(data.message || 'Initialisation du système RAG...')
            break

          case 'rag_loading_complete':
            setRagLoading(false)
            setRagLoadingMessage('')
            break

          case 'rag_loading_error':
            setRagLoading(false)
            setRagLoadingMessage('')
            console.error('RAG loading error:', data.error)
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

  const connect = useCallback(async (agentId: string, options?: { deviceId?: string }) => {
    try {
      setError(null)
      setConnectionState('connecting')
      await liveKitClient.connect(agentId, options)
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
        setLocalAudioStream(null)
      }
    } catch (err) {
      console.error('Disconnect failed:', err)
    }
  }, [])

  const switchMicrophone = useCallback(async (deviceId?: string) => {
    try {
      await liveKitClient.switchMicrophone(deviceId)
      // The local audio stream will be updated via onLocalAudioTrack event
    } catch (err) {
      if (isMounted.current) {
        const message = err instanceof Error ? err.message : 'Failed to switch microphone'
        setError(message)
      }
      throw err
    }
  }, [])

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
    switchMicrophone
  }
}