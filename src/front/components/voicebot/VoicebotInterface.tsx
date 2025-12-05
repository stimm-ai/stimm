'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Agent } from '@/components/agent/types'
import { useLiveKit } from '@/hooks/use-livekit'
import { useMicrophoneDevices } from '@/hooks/use-microphone-devices'
import { Mic, MicOff, MoreHorizontal, X, MessageSquare, Activity, Settings, Zap, Bot, User } from 'lucide-react'
import Image from 'next/image'
import logo from '@/assets/logo_stimm_h.png'

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

// Reverting to original gradient theme but adapting to the new layout
const THEME = {
  bg: 'bg-gradient-to-br from-[#3A2868] to-[#6481B3]',
  panel: 'bg-white/10 backdrop-blur-md',
  border: 'border-white/20',
  text: 'text-white',
  textMuted: 'text-gray-200',
  accent: 'text-[#E7348C]',
  success: 'text-green-300',
  error: 'text-red-300'
}

export function VoicebotInterface() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string>('default')
  const [currentAgent, setCurrentAgent] = useState<Agent | null>(null)

  const [status, setStatus] = useState<VoicebotStatus>({
    energy: 0,
    state: 'silence',
    llmStatus: false,
    ttsStatus: false,
    tokenCount: 0,
    audioChunkCount: 0,
    streamTime: 0
  })
  const [showAgentOverlay, setShowAgentOverlay] = useState(false)

  const [transcription, setTranscription] = useState<string>('')
  const [response, setResponse] = useState<string>('')

  // Use the LiveKit hook
  const {
    isConnected,
    connectionState,
    agentParticipant,
    audioStream,
    localAudioStream,
    error: liveKitError,
    transcription: liveTranscripts,
    response: liveResponse,
    vadState,
    llmState,
    ttsState,
    metrics,
    turnState,
    connect,
    disconnect,
    switchMicrophone
  } = useLiveKit()

  // Microphone devices
  const {
    devices,
    selectedDeviceId,
    isLoading: devicesLoading,
    error: devicesError,
    refreshDevices,
    setSelectedDeviceId,
  } = useMicrophoneDevices()

  const selectedDevice = devices.find(d => d.deviceId === selectedDeviceId)
  const tooltipText = selectedDevice ? selectedDevice.label : 'Select microphone'

  const audioPlayerRef = useRef<HTMLAudioElement>(null)

  // Visualizer State
  const [audioLevels, setAudioLevels] = useState<number[]>([0, 0, 0, 0, 0])
  const [activeStreamType, setActiveStreamType] = useState<'user' | 'agent'>('user')
  const animationRef = useRef<number>()
  const analyserRef = useRef<AnalyserNode>()
  const audioContextRef = useRef<AudioContext>()

  // Load agents on component mount
  useEffect(() => {
    loadAgents()
  }, [])

  // Update current agent object when selection changes or agents load
  useEffect(() => {
    if (agents.length > 0) {
      const agent = agents.find(a => a.id === selectedAgentId)
      if (agent) {
        setCurrentAgent(agent)
      } else {
        // If selectedAgentId doesn't match any agent, select the first one
        setSelectedAgentId(agents[0].id)
        setCurrentAgent(agents[0])
      }
    }
  }, [selectedAgentId, agents])

  // Track previous selected device ID to avoid unnecessary switches
  const prevDeviceIdRef = useRef<string | undefined>(selectedDeviceId)

  // Switch microphone when device changes while connected
  useEffect(() => {
    if (isConnected && selectedDeviceId !== prevDeviceIdRef.current) {
      prevDeviceIdRef.current = selectedDeviceId
      switchMicrophone(selectedDeviceId || undefined).catch(err => {
        console.error('Failed to switch microphone:', err)
        // Optionally show error to user
      })
    } else {
      prevDeviceIdRef.current = selectedDeviceId
    }
  }, [selectedDeviceId, isConnected, switchMicrophone])

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

  // Setup Web Audio API for Real-time Visualizer
  useEffect(() => {
    // Determine which stream to visualize
    // If agent is speaking (responding state or playing audio), use agent stream
    // Otherwise use local mic
    const isAgentSpeaking = status.state === 'responding' || turnState.webrtc_streaming_agent_audio_response_started
    // Prioritize audioStream only if it exists and agent is supposedly speaking
    const targetStream = (isAgentSpeaking && audioStream) ? audioStream : localAudioStream
    const type = (isAgentSpeaking && audioStream) ? 'agent' : 'user'

    setActiveStreamType(type)

    if (!targetStream) {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
      setAudioLevels([0, 0, 0, 0, 0])
      return
    }

    const initAudioContext = () => {
      try {
        // Reuse context if exists and running, or create new
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
             audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
        }
        const audioContext = audioContextRef.current

        // Ensure we don't have dangling analysers/animations
        if (animationRef.current) cancelAnimationFrame(animationRef.current)

        const analyser = audioContext.createAnalyser()
        // Note: createMediaStreamSource can throw if stream is not active or valid
        const source = audioContext.createMediaStreamSource(targetStream)

        analyser.fftSize = 32 // Small FFT size for fewer bars
        source.connect(analyser)

        analyserRef.current = analyser

        const bufferLength = analyser.frequencyBinCount
        const dataArray = new Uint8Array(bufferLength)

        const updateVisualizer = () => {
          if (!analyserRef.current) return

          // Gate for user microphone based on VAD to avoid parasitic noise
          // If we are in user mode (listening) and VAD is NOT active/speaking, show zero levels
          // We use status.state which comes from backend VAD, or a local threshold if needed
          // The user specifically requested this to filter out idle noise
          const isUserMode = type === 'user'
          const isVadActive = status.state === 'speaking' || turnState.vad_speech_detected

          if (isUserMode && !isVadActive) {
             // Decay levels to 0 smoothly or set to 0
             setAudioLevels(prev => prev.map(l => Math.max(0, l - 5)))
             animationRef.current = requestAnimationFrame(updateVisualizer)
             return
          }

          analyserRef.current.getByteFrequencyData(dataArray)

          // Map frequency bins to 5 bars
          // Indices: 0 (Bass), 1, 2 (Mids), 3, 4 (Treble)
          const indices = [1, 2, 3, 5, 8]
          const levels = indices.map(i => {
             const val = dataArray[i] || 0
             // Scale 0-255 to 0-100
             return (val / 255) * 100
          })

          setAudioLevels(levels)
          animationRef.current = requestAnimationFrame(updateVisualizer)
        }

        updateVisualizer()
      } catch (e) {
        console.error('Failed to initialize audio visualizer:', e)
      }
    }

    initAudioContext()

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
      // We generally keep audioContext alive, but could close it if component unmounts
    }
  }, [localAudioStream, audioStream, status.state, turnState.webrtc_streaming_agent_audio_response_started, turnState.vad_speech_detected])

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
      playbackStartLatency: metrics?.latency || 0
    }))
  }, [liveTranscripts, liveResponse, vadState, llmState, ttsState, metrics])

  const loadAgents = async () => {
    try {
      const WSL2_IP = '172.23.126.232'
      const response = await fetch(`http://${WSL2_IP}:8001/api/agents/`)
      if (response.ok) {
        const agentsData = await response.json()
        setAgents(agentsData)
        console.log('Loaded agents:', agentsData.length)
        
        // Fetch and select the default agent
        try {
          const defaultResponse = await fetch(`http://${WSL2_IP}:8001/api/agents/default/current`)
          if (defaultResponse.ok) {
            const defaultAgent = await defaultResponse.json()
            setSelectedAgentId(defaultAgent.id)
            setCurrentAgent(defaultAgent)
            console.log('Selected default agent:', defaultAgent.name)
          }
        } catch (defaultErr) {
          console.warn('Failed to load default agent, using first agent:', defaultErr)
          if (agentsData.length > 0) {
            setSelectedAgentId(agentsData[0].id)
            setCurrentAgent(agentsData[0])
          }
        }
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
      if (connectionState === 'connecting') return
      await connect(selectedAgentId, { deviceId: selectedDeviceId || undefined })
    } else {
      await disconnect()
      setTranscription('')
      setResponse('')
    }
  }

  return (
    <div className={`min-h-screen ${THEME.bg} text-white font-sans p-4 flex gap-4 overflow-hidden`}>
       {/* CENTER PANEL: Visualizer & Controls */}
       <div className="flex-1 flex flex-col relative rounded-xl border border-white/20 bg-white/10 backdrop-blur-sm overflow-hidden shadow-2xl">
         {/* Top Header - Agent Selector */}
         <div className="absolute top-0 left-0 right-0 p-6 flex justify-between items-start z-10">
           <div className="flex flex-col gap-1">
             <Image src={logo} alt="Stimm" width={120} height={33} className="drop-shadow-md" />
             <p className="text-xs text-white/70 uppercase tracking-widest">Your voice agent</p>
           </div>
           <div className="flex items-center gap-4">
              {/* Agent Selection Button */}
              <Button
                onClick={() => setShowAgentOverlay(!showAgentOverlay)}
                className="px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 text-white flex items-center gap-2 transition-all shadow-lg"
              >
                <Bot className="w-3 h-3" />
                <span>{currentAgent?.name || 'Select Agent'}</span>
                <span className="text-xs text-white/60">▼</span>
              </Button>
           </div>
         </div>
         {/* Custom Agent Selection Overlay */}
         {showAgentOverlay && (
           <div className="fixed inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-50">
             <div className="bg-gradient-to-br from-blue-900 to-purple-900 border border-white/20 rounded-xl p-6 shadow-2xl w-full max-w-4xl mx-4">
               <div className="flex justify-between items-center mb-4">
                 <h3 className="text-xl font-bold text-white">Select Voice Agent</h3>
                 <button
                   className="text-white/60 hover:text-white transition-colors"
                   onClick={() => setShowAgentOverlay(false)}
                 >
                   <X className="w-5 h-5" />
                 </button>
               </div>
               <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                 {agents.map(agent => (
                   <div
                     key={agent.id}
                     onClick={() => {
                       setSelectedAgentId(agent.id);
                       setShowAgentOverlay(false);
                     }}
                     className={`px-4 py-5 rounded-lg border-2 transition-all cursor-pointer
                       ${selectedAgentId === agent.id
                         ? 'border-[#E7348C] bg-[#3A2868]/50 text-white shadow-[0_0_20px_rgba(231,52,140,0.3)]'
                         : 'border-white/10 bg-white/5 hover:bg-white/10 text-white/80 hover:text-white'
                       }`}
                   >
                     <div className="font-bold text-white uppercase mb-2">{agent.name}</div>
                     <div className="text-[10px] text-white/60">{agent.description || 'Voice AI Agent'}</div>
                     <div className="mt-3 flex items-center gap-2">
                       <span className="text-xs bg-[#E7348C]/20 px-2 py-1 rounded-full">{agent.stt_provider || 'Deepgram'}</span>
                       <span className="text-xs bg-purple-400/20 px-2 py-1 rounded-full">{agent.llm_provider || 'Mistral'}</span>
                     </div>
                   </div>
                 ))}
               </div>
             </div>
           </div>
         )}
         {/* Center: VAD Visualizer */}
         <div className="flex-1 flex flex-col items-center justify-center p-8 relative">
           {/* Container for both start button and visualizer with transition */}
           <div className="flex flex-col items-center justify-center h-52 w-full relative">
             {/* Transition container */}
             <div className={`flex flex-col items-center justify-center h-full w-full absolute
               ${isConnected ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}
               transition-opacity duration-300 ease-in-out transition-transform duration-300 ease-in-out`}>
               {/* Visualizer Icon Indicator */}
               <div className="mb-6 flex justify-center h-8">
                 <div className={`
                   flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider transition-all duration-300
                   ${activeStreamType === 'agent'
                     ? 'bg-[#E7348C]/20 text-[#E7348C] border border-[#E7348C]/30 shadow-[0_0_15px_rgba(231,52,140,0.3)]'
                     : 'bg-white/10 text-white/70 border border-white/10'}
                 `}>
                   {activeStreamType === 'agent' ? <Bot className="w-3 h-3" /> : <User className="w-3 h-3" />}
                   <span>{activeStreamType === 'agent' ? 'Agent Speaking' : 'Listening'}</span>
                 </div>
               </div>

               {/* Visualizer Bars */}
               <div className="flex items-center justify-center gap-3 h-32">
                 {audioLevels.map((level, i) => {
                   // Enhance levels for better visibility
                   const shapeMultipliers = [0.8, 1.0, 1.2, 1.0, 0.8]
                   const height = Math.max(15, level * shapeMultipliers[i])

                   const isActive = level > 5
                   const isAgent = activeStreamType === 'agent'

                   return (
                     <div
                       key={i}
                       className={`w-12 rounded-full transition-all duration-75 ease-out shadow-lg
                         ${isActive
                           ? (isAgent ? 'bg-[#E7348C] shadow-[0_0_20px_rgba(231,52,140,0.6)]' : 'bg-white shadow-[0_0_20px_rgba(255,255,255,0.6)]')
                           : (isAgent ? 'bg-[#3A2868]/40' : 'bg-white/20')
                         }`}
                       style={{
                         height: `${Math.min(100, height)}%`,
                         opacity: isActive ? 0.8 + (level / 200) : 0.3
                       }}
                     />
                   )
                 })}
               </div>
             </div>

             {/* Start Button Container with transition */}
             <div className={`flex flex-col items-center justify-center h-60 absolute
               ${isConnected ? 'opacity-0 scale-90 pointer-events-none' : 'opacity-100 scale-100'}
               transition-all duration-300 ease-in-out`}>
               <Button
                 onClick={handleVoiceToggle}
                 className="w-24 h-24 rounded-full bg-white text-indigo-600 hover:bg-gray-100 shadow-[0_0_30px_rgba(255,255,255,0.9)] flex items-center justify-center mb-2 transition-all transform hover:scale-105"
               >
                 <Mic className="w-12 h-12" />
               </Button>
               <span className="text-white/80 text-sm">Start Conversation</span>
             </div>
           </div>

           {/* Connection Status Text */}
           <div className="mt-8 text-center h-8 font-medium drop-shadow-md">
             {connectionState === 'connecting' && <span className="text-yellow-300 animate-pulse">Connecting...</span>}
             {connectionState === 'connected' && <span className="text-green-300">Connected to {currentAgent?.name}</span>}
             {connectionState === 'failed' && <span className="text-red-300">{liveKitError || 'Connection Failed'}</span>}
           </div>

           {/* Microphone Settings Selector - positioned in bottom right of center panel */}
           <div className="absolute bottom-4 right-4 z-10">
             <Select
               value={selectedDeviceId || ''}
               onValueChange={setSelectedDeviceId}
               disabled={devicesLoading || devices.length === 0}
             >
               <SelectTrigger
                 className="h-12 w-auto px-4 rounded-full bg-black/30 border border-white/10 text-white/70 hover:text-white hover:bg-white/20 data-[state=open]:bg-white/20 gap-2"
                 aria-label="Select microphone"
                 title={tooltipText}
               >
                 <Mic className="w-5 h-5" />
               </SelectTrigger>
               <SelectContent className="bg-black/80 backdrop-blur-md border border-white/10 text-white">
                 {devicesLoading ? (
                   <SelectItem value="loading" disabled>Loading microphones...</SelectItem>
                 ) : devicesError ? (
                   <SelectItem value="error" disabled>Error loading devices</SelectItem>
                 ) : devices.length === 0 ? (
                   <SelectItem value="none" disabled>No microphones found</SelectItem>
                 ) : (
                   devices.map((device) => (
                     <SelectItem key={device.deviceId} value={device.deviceId}>
                       {device.label}
                     </SelectItem>
                   ))
                 )}
               </SelectContent>
             </Select>
           </div>
         </div>

         {/* Bottom: Hangup Button - only shown when connected */}
         {isConnected && (
           <div className="absolute bottom-10 left-0 right-0 flex justify-center items-center z-10">
             <div className="flex items-center bg-black/20 backdrop-blur-md rounded-full p-1 border border-white/10 shadow-xl">
               <Button
                 variant="ghost"
                 size="icon"
                 onClick={disconnect}
                 className="w-14 h-14 rounded-full bg-red-500/80 text-white hover:bg-red-600/90 shadow-[0_0_15px_rgba(220,38,38,0.5)] transition-all"
               >
                 <X className="w-6 h-6" />
               </Button>
             </div>
           </div>
         )}

         {/* Hidden Audio Element */}
         <audio ref={audioPlayerRef} className="hidden" />
       </div>

       {/* RIGHT PANEL: Sidebar */}
       <div className="w-[380px] flex flex-col gap-6 p-4 rounded-xl border border-white/10 bg-black/20 backdrop-blur-md overflow-hidden shadow-xl">
         {/* Agent Configuration */}
         <div className="space-y-4">
            <h3 className="text-xs font-bold text-white/60 uppercase tracking-wider flex items-center gap-2 border-b border-white/10 pb-2">
              <Settings className="w-3 h-3" /> Agent details
            </h3>

            <div className="grid grid-cols-[1fr_auto] gap-y-3 text-xs">
               {/* VAD */}
               <div className="text-white/80 font-semibold">VAD</div>
               <div className="text-[#E7348C] font-mono text-right">SILERO</div>

               {/* STT */}
               <div className="text-white/80 font-semibold pt-1">SPEECH-TO-TEXT</div>
               <div className="text-[#E7348C] font-mono text-right pt-1 uppercase">
                 {currentAgent?.stt_provider || 'DEEPGRAM'}
               </div>
               <div className="text-white/50 pl-2">MODEL</div>
               <div className="text-[#E7348C]/80 font-mono text-right uppercase">
                 {currentAgent?.stt_config?.model || 'NOVA-3'}
               </div>

               {/* LLM */}
               <div className="text-white/80 font-semibold pt-1">LLM</div>
               <div className="text-[#E7348C] font-mono text-right uppercase">
                 {currentAgent?.llm_provider || 'OPENAI'}
               </div>
               <div className="text-white/50 pl-2">MODEL</div>
               <div className="text-[#E7348C]/80 font-mono text-right uppercase">
                 {currentAgent?.llm_config?.model || 'GPT-4.0-MINI'}
               </div>

               {/* TTS */}
               <div className="text-white/80 font-semibold pt-1">TEXT-TO-SPEECH</div>
               <div className="text-[#E7348C] font-mono text-right uppercase">
                  {currentAgent?.tts_provider || 'ELEVENLABS'}
               </div>
               <div className="text-white/50 pl-2">MODEL</div>
               <div className="text-[#E7348C]/80 font-mono text-right uppercase">
                  {currentAgent?.tts_config?.model || 'FLASH_V2_5'}
               </div>
               <div className="text-white/50 pl-2">VOICE</div>
               <div className="text-[#E7348C]/80 font-mono text-right uppercase truncate max-w-[150px]" title={currentAgent?.tts_config?.voice}>
                  {currentAgent?.tts_config?.voice || '-'}
               </div>
            </div>
         </div>

         {/* Live Metrics / Status Indicators */}
         <div className="space-y-4">
            <h3 className="text-xs font-bold text-white/60 uppercase tracking-wider flex items-center gap-2 border-b border-white/10 pb-2">
              <Zap className="w-3 h-3" /> Live Status
            </h3>

            <div className="grid grid-cols-[1fr_auto] gap-y-3 text-xs items-center">
               {/* Indicators */}
               <div className="text-white/80">SPEECH DETECTED</div>
               <div className={`h-2 w-2 rounded-full ${turnState.vad_speech_detected && !turnState.vad_end_of_speech_detected ? 'bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.8)]' : 'bg-white/10'}`} />

               <div className="text-white/80">STT STREAMING</div>
               <div className={`h-2 w-2 rounded-full ${turnState.stt_streaming_started && !turnState.stt_streaming_ended ? 'bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)]' : 'bg-white/10'}`} />

               <div className="text-white/80">LLM STREAMING</div>
               <div className={`h-2 w-2 rounded-full ${turnState.llm_streaming_started && !turnState.llm_streaming_ended ? 'bg-purple-400 shadow-[0_0_8px_rgba(192,132,252,0.8)]' : 'bg-white/10'}`} />

               <div className="text-white/80">TTS STREAMING</div>
               <div className={`h-2 w-2 rounded-full ${turnState.tts_streaming_started && !turnState.tts_streaming_ended ? 'bg-orange-400 shadow-[0_0_8px_rgba(251,146,60,0.8)]' : 'bg-white/10'}`} />

               {/* Overall Latency */}
               <div className="text-white font-bold pt-2">RESPONSE LATENCY</div>
               <div className="text-[#E7348C] font-bold font-mono text-right pt-2 text-sm">
                  {status.firstChunkLatency ? `${Math.round(status.firstChunkLatency || 0)}ms` : '-'}
               </div>
            </div>
         </div>

         {/* Live Transcription */}
         <div className="flex-1 flex flex-col min-h-0 border-t border-white/10 pt-4">
            <h3 className="text-xs font-bold text-white/60 uppercase tracking-wider mb-4 flex items-center gap-2">
              <MessageSquare className="w-3 h-3" /> Transcription
            </h3>

            <div className="flex-1 overflow-y-auto text-sm space-y-4 pr-2 font-mono leading-relaxed custom-scrollbar">
               {transcription && (
                 <div className="space-y-1 animate-in fade-in slide-in-from-bottom-2">
                    <div className="text-xs text-white/50 uppercase">You</div>
                    <div className="text-white/90">{transcription}</div>
                 </div>
               )}

               {response && (
                 <div className="space-y-1 animate-in fade-in slide-in-from-bottom-2">
                    <div className="text-xs text-[#E7348C]/70 uppercase">Agent</div>
                    <div className="text-[#E7348C]">{response}</div>
                 </div>
               )}

               {!transcription && !response && (
                 <div className="text-white/40 italic text-xs">
                    Waiting for conversation to start...
                 </div>
               )}
            </div>
         </div>
       </div>

    </div>
  )
}
