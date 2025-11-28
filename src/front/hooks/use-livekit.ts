'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { liveKitClient } from '@/lib/livekit-client'
import { RemoteParticipant } from 'livekit-client'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed'

export interface UseLiveKitReturn {
  isConnected: boolean
  connectionState: ConnectionState
  agentParticipant: RemoteParticipant | null
  audioStream: MediaStream | null
  error: string | null
  connect: (agentId: string) => Promise<void>
  disconnect: () => Promise<void>
}

export function useLiveKit(): UseLiveKitReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [agentParticipant, setAgentParticipant] = useState<RemoteParticipant | null>(null)
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  
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
    connect,
    disconnect
  }
}