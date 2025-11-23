'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Agent } from '@/components/agent/types'
import { WebRTCVoiceClient } from '@/lib/webrtc-client'

interface VoicebotStatus {
  energy: number
  state: 'silence' | 'speaking' | 'processing' | 'responding'
  isConnected: boolean
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'failed' | 'closed'
  llmStatus: boolean
  ttsStatus: boolean
  tokenCount: number
  audioChunkCount: number
  streamTime: number
  firstChunkLatency?: number
  playbackStartLatency?: number
}

export function VoicebotInterface() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('default')
  const [status, setStatus] = useState<VoicebotStatus>({
    energy: 0,
    state: 'silence',
    isConnected: false,
    connectionState: 'disconnected',
    llmStatus: false,
    ttsStatus: false,
    tokenCount: 0,
    audioChunkCount: 0,
    streamTime: 0
  })
  
  const [transcription, setTranscription] = useState<string>('Your speech will appear here in real-time...')
  const [response, setResponse] = useState<string>('Assistant responses will appear here...')
  const [error, setError] = useState<string | null>(null)
  
  const webrtcClientRef = useRef<WebRTCVoiceClient | null>(null)
  const audioPlayerRef = useRef<HTMLAudioElement>(null)
  const streamStartTimeRef = useRef<number>(0)
  const firstChunkTimeRef = useRef<number>(0)

  // Load agents on component mount
  useEffect(() => {
    loadAgents()
  }, [])

  // Initialize WebRTC client
  useEffect(() => {
    webrtcClientRef.current = new WebRTCVoiceClient()
    
    const client = webrtcClientRef.current
    
    // Set up event handlers
    client.onConnectionStateChange = (state: string) => {
      setStatus(prev => ({ ...prev, connectionState: state as any }))
    }
    
    client.onAudioTrack = (stream: MediaStream) => {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.srcObject = stream
        audioPlayerRef.current.play().catch(console.error)
      }
    }
    
    client.onVADUpdate = (energy: number, state: string) => {
      setStatus(prev => ({ ...prev, energy, state: state as any }))
    }
    
    client.onTranscription = (text: string) => {
      setTranscription(text)
    }
    
    client.onResponse = (text: string) => {
      setResponse(text)
    }
    
    client.onStatusUpdate = (statusUpdate: Partial<VoicebotStatus>) => {
      setStatus(prev => ({ ...prev, ...statusUpdate }))
    }
    
    client.onError = (errorMessage: string) => {
      setError(errorMessage)
    }

    return () => {
      client.disconnect()
    }
  }, [])

  const loadAgents = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/agents/')
      if (response.ok) {
        const agents = await response.json()
        setAgents(agents)
        console.log('Loaded agents:', agents.length)
      } else {
        console.warn('Failed to load agents, status:', response.status)
        setAgents([])
      }
    } catch (err) {
      console.warn('Failed to load agents:', err)
      setAgents([])
    }
  }

  const handleVoiceToggle = async () => {
    if (!status.isConnected) {
      // Connect
      try {
        setError(null)
        streamStartTimeRef.current = Date.now()
        firstChunkTimeRef.current = 0
        
        setStatus(prev => ({ ...prev, connectionState: 'connecting' }))
        
        await webrtcClientRef.current?.connect(selectedAgent)
        
        setStatus(prev => ({ 
          ...prev, 
          isConnected: true, 
          connectionState: 'connected',
          streamTime: 0 
        }))
      } catch (err) {
        console.error('Connection failed:', err)
        setError(err instanceof Error ? err.message : 'Connection failed')
        setStatus(prev => ({ ...prev, connectionState: 'failed' }))
      }
    } else {
      // Disconnect
      webrtcClientRef.current?.disconnect()
      setStatus(prev => ({ 
        ...prev, 
        isConnected: false, 
        connectionState: 'disconnected',
        state: 'silence',
        energy: 0 
      }))
      setTranscription('Your speech will appear here in real-time...')
      setResponse('Assistant responses will appear here...')
    }
  }

  const getButtonText = () => {
    switch (status.connectionState) {
      case 'connecting': return '⏳ Connecting...'
      case 'connected': return '🛑 Stop Conversation'
      case 'failed': return '❌ Connection Failed'
      default: return '🎤 Start Conversation'
    }
  }

  const getButtonClass = () => {
    switch (status.connectionState) {
      case 'connecting': return 'bg-gray-500 text-white'
      case 'connected': return 'bg-red-500 text-white'
      case 'failed': return 'bg-orange-500 text-white'
      default: return 'bg-green-500 text-white hover:bg-green-600'
    }
  }

  const formatLatency = (latency?: number) => {
    if (!latency) return '-'
    return `${Math.round(latency)}ms`
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 p-4">
      <div className="max-w-6xl mx-auto bg-white rounded-2xl shadow-2xl h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white p-6 text-center">
          <h1 className="text-2xl font-semibold mb-2">Voicebot Assistant</h1>
          <p className="opacity-90">Complete voice conversation with STT, RAG/LLM, and TTS integration</p>
        </div>

        {/* Status Bar */}
        <div className="bg-gray-50 p-4 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${
                status.connectionState === 'connected' ? 'bg-green-500 animate-pulse' :
                status.connectionState === 'failed' ? 'bg-red-500' : 'bg-gray-400'
              }`} />
              <span className="text-sm font-medium capitalize">
                {status.connectionState === 'disconnected' ? 'Ready to connect' : status.connectionState}
              </span>
            </div>
            
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Agent:</label>
              <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Loading agents..." />
                </SelectTrigger>
                <SelectContent>
                  {agents.length > 0 ? (
                    agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))
                  ) : (
                    <SelectItem value="default">Default Agent</SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            
            <div className="text-xs text-gray-500">
              Energy: {status.energy.toFixed(3)} | State: {status.state}
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="mx-4 mt-4 border-red-200 bg-red-50">
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}

        {/* Voice Controls */}
        <div className="p-8 text-center bg-white">
          <Button
            onClick={handleVoiceToggle}
            disabled={status.connectionState === 'connecting'}
            className={`px-8 py-4 text-lg font-semibold rounded-full min-w-48 shadow-lg transition-all hover:scale-105 ${getButtonClass()}`}
          >
            {getButtonText()}
          </Button>
          
          {/* VAD Visualizer */}
          <div className="mt-4 mx-auto w-80 max-w-sm">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-green-500 transition-all duration-100 rounded-full"
                style={{ width: `${Math.min(status.energy * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex gap-4 p-4 overflow-hidden">
          {/* Transcription Panel */}
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>Transcription</CardTitle>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="h-48 overflow-y-auto text-gray-700 leading-relaxed whitespace-pre-wrap">
                {transcription}
              </div>
            </CardContent>
          </Card>

          {/* Response Panel */}
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>Assistant Response</CardTitle>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="h-48 overflow-y-auto text-gray-700 leading-relaxed whitespace-pre-wrap">
                {response}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Status Section */}
        <div className="bg-gray-50 border-t border-gray-200 p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-600">🔄 LLM Sending:</span>
              <div className={`w-3 h-3 rounded-full ${status.llmStatus ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-600">🔊 TTS Receiving:</span>
              <div className={`w-3 h-3 rounded-full ${status.ttsStatus ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            </div>
            <div className="text-gray-600">
              <span>Tokens: {status.tokenCount}</span>
            </div>
            <div className="text-gray-600">
              <span>Audio Chunks: {status.audioChunkCount}</span>
            </div>
          </div>

          {/* Latency Section */}
          {(status.firstChunkLatency || status.playbackStartLatency) && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg border-l-4 border-blue-400">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex justify-between items-center">
                  <span className="font-medium">⏱️ First Audio Chunk:</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    status.firstChunkLatency 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {formatLatency(status.firstChunkLatency)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-medium">🎵 Audio Playback Start:</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    status.playbackStartLatency 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {formatLatency(status.playbackStartLatency)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Hidden Audio Player */}
        <audio ref={audioPlayerRef} className="hidden" />
      </div>
    </div>
  )
}