'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Agent } from '@/components/agent/types'
import { useLiveKit } from '@/hooks/use-livekit'

interface VoicebotStatus {
  energy: number
  state: 'silence' | 'speaking' | 'processing' | 'responding'
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
    llmStatus: false,
    ttsStatus: false,
    tokenCount: 0,
    audioChunkCount: 0,
    streamTime: 0
  })
  
  const [transcription, setTranscription] = useState<string>('Your speech will appear here in real-time...')
  const [response, setResponse] = useState<string>('Assistant responses will appear here...')
  
  // Use the LiveKit hook
  const {
    isConnected,
    connectionState,
    agentParticipant,
    audioStream,
    error: liveKitError,
    transcription: liveTranscripts,
    response: liveResponse,
    vadState,
    llmState,
    ttsState,
    metrics,
    turnState,
    connect,
    disconnect
  } = useLiveKit()
  
  const audioPlayerRef = useRef<HTMLAudioElement>(null)

  // Load agents on component mount
  useEffect(() => {
    loadAgents()
  }, [])

  // Handle Audio Stream
  useEffect(() => {
    if (audioPlayerRef.current) {
      if (audioStream) {
        console.log('Attaching audio stream to player')
        audioPlayerRef.current.srcObject = audioStream
        audioPlayerRef.current.play().catch(e => console.error('Audio playback failed:', e))
      } else {
        audioPlayerRef.current.srcObject = null
      }
    }
  }, [audioStream])

  // Sync LiveKit Data to Local State for UI
  useEffect(() => {
    if (liveTranscripts) {
      setTranscription(liveTranscripts)
    }
    if (liveResponse) {
      setResponse(liveResponse)
    }
    
    // Update status object with all indicators
    setStatus(prev => ({
      ...prev,
      // VAD
      energy: vadState?.energy || 0,
      state: vadState?.state || 'silence',
      // Status indicators
      llmStatus: llmState,
      ttsStatus: ttsState,
      // Metrics
      tokenCount: metrics?.tokens || 0,
      audioChunkCount: metrics?.audioChunks || 0,
      firstChunkLatency: metrics?.latency || 0,
      // playbackStartLatency is usually close to firstChunkLatency in this setup
      playbackStartLatency: metrics?.latency || 0
    }))
  }, [liveTranscripts, liveResponse, vadState, llmState, ttsState, metrics])

  const loadAgents = async () => {
    try {
      // Use environment-aware logic from frontend-config (but here we hardcode for now as per original)
      // Or better, use the proxy or direct IP if known.
      // Keeping original logic for fetching agents list
      const WSL2_IP = '172.23.126.232'
      const response = await fetch(`http://${WSL2_IP}:8001/api/agents/`)
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
    if (!isConnected) {
      // Connect
      if (connectionState === 'connecting') return
      await connect(selectedAgent)
    } else {
      // Disconnect
      await disconnect()
      setTranscription('Your speech will appear here in real-time...')
      setResponse('Assistant responses will appear here...')
    }
  }

  const getButtonText = () => {
    switch (connectionState) {
      case 'connecting': return '⏳ Connecting...'
      case 'connected': return '🛑 Stop Conversation'
      case 'failed': return '❌ Connection Failed'
      case 'reconnecting': return '🔄 Reconnecting...'
      default: return '🎤 Start Conversation'
    }
  }

  const getButtonClass = () => {
    switch (connectionState) {
      case 'connecting': return 'bg-gray-500 text-white'
      case 'connected': return 'bg-red-500 text-white'
      case 'failed': return 'bg-orange-500 text-white'
      case 'reconnecting': return 'bg-yellow-500 text-white'
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
          <h1 className="text-2xl font-semibold mb-2">Voicebot Assistant (LiveKit)</h1>
          <p className="opacity-90">Complete voice conversation with STT, RAG/LLM, and TTS integration</p>
        </div>

        {/* Status Bar */}
        <div className="bg-gray-50 p-4 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${
                connectionState === 'connected' ? 'bg-green-500 animate-pulse' :
                connectionState === 'failed' ? 'bg-red-500' : 
                connectionState === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-gray-400'
              }`} />
              <span className="text-sm font-medium capitalize">
                {connectionState === 'disconnected' ? 'Ready to connect' : connectionState}
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
               {agentParticipant ? `Connected to Agent: ${agentParticipant.identity}` : 'No Agent Connected'}
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {liveKitError && (
          <Alert className="mx-4 mt-4 border-red-200 bg-red-50">
            <AlertDescription className="text-red-800">{liveKitError}</AlertDescription>
          </Alert>
        )}

        {/* Voice Controls */}
        <div className="p-8 text-center bg-white">
          <Button
            onClick={handleVoiceToggle}
            disabled={connectionState === 'connecting'}
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
            <div className="text-xs text-gray-500 mt-1 flex justify-between">
               <span>VAD State: {status.state}</span>
               <span>Energy: {status.energy.toFixed(2)}</span>
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
              <div className="h-48 overflow-y-auto text-gray-700 leading-relaxed whitespace-pre-wrap font-mono text-sm">
                {transcription || <span className="text-gray-400 italic">Waiting for speech...</span>}
              </div>
            </CardContent>
          </Card>

          {/* Response Panel */}
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>Assistant Response</CardTitle>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="h-48 overflow-y-auto text-gray-700 leading-relaxed whitespace-pre-wrap font-mono text-sm">
                {response || <span className="text-gray-400 italic">Waiting for response...</span>}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Status Section */}
        <div className="bg-gray-50 border-t border-gray-200 p-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm mb-4">
             {/* Turn State Indicators */}
             <div className="flex flex-col gap-1">
               <span className="text-xs font-semibold text-gray-500">VAD Speech</span>
               <div className={`w-full h-2 rounded-full ${turnState.vad_speech_detected && !turnState.vad_end_of_speech_detected ? 'bg-green-500' : 'bg-gray-300'}`} />
             </div>
             
             <div className="flex flex-col gap-1">
               <span className="text-xs font-semibold text-gray-500">STT Streaming</span>
               <div className={`w-full h-2 rounded-full ${turnState.stt_streaming_started && !turnState.stt_streaming_ended ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} />
             </div>

             <div className="flex flex-col gap-1">
               <span className="text-xs font-semibold text-gray-500">LLM Streaming</span>
               <div className={`w-full h-2 rounded-full ${turnState.llm_streaming_started && !turnState.llm_streaming_ended ? 'bg-purple-500 animate-pulse' : 'bg-gray-300'}`} />
             </div>

             <div className="flex flex-col gap-1">
               <span className="text-xs font-semibold text-gray-500">TTS Streaming</span>
               <div className={`w-full h-2 rounded-full ${turnState.tts_streaming_started && !turnState.tts_streaming_ended ? 'bg-orange-500 animate-pulse' : 'bg-gray-300'}`} />
             </div>

             <div className="flex flex-col gap-1">
               <span className="text-xs font-semibold text-gray-500">Agent Audio</span>
               <div className={`w-full h-2 rounded-full ${turnState.webrtc_streaming_agent_audio_response_started && !turnState.webrtc_streaming_agent_audio_response_ended ? 'bg-red-500 animate-pulse' : 'bg-gray-300'}`} />
             </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm border-t border-gray-200 pt-3">
             <div className="flex items-center justify-between">
                <span className="text-gray-600">State:</span>
                <span className="font-mono font-medium">{turnState.vad_state}</span>
             </div>
             <div className="flex items-center justify-between">
                <span className="text-gray-600">Response Delay:</span>
                <span className={`font-mono font-medium ${turnState.agent_response_delay ? 'text-green-600' : 'text-gray-400'}`}>
                  {turnState.agent_response_delay ? `${Math.round(turnState.agent_response_delay * 1000)}ms` : '-'}
                </span>
             </div>
             <div className="flex items-center justify-between">
               <span className="text-gray-600">Tokens:</span>
               <span className="font-mono">{status.tokenCount}</span>
             </div>
             <div className="flex items-center justify-between">
               <span className="text-gray-600">Audio Chunks:</span>
               <span className="font-mono">{status.audioChunkCount}</span>
             </div>
          </div>
        </div>

        {/* Hidden Audio Player */}
        <audio ref={audioPlayerRef} className="hidden" />
      </div>
    </div>
  )
}