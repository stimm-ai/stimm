'use client'

interface WebRTCEvents {
  onConnectionStateChange?: (state: string) => void
  onAudioTrack?: (stream: MediaStream) => void
  onVADUpdate?: (energy: number, state: string) => void
  onTranscription?: (text: string) => void
  onResponse?: (text: string) => void
  onStatusUpdate?: (status: any) => void
  onError?: (error: string) => void
}

export class WebRTCVoiceClient {
  private peerConnection: RTCPeerConnection | null = null
  private localStream: MediaStream | null = null
  private events: WebRTCEvents = {}
  private sessionId: string | null = null
  private dataChannel: RTCDataChannel | null = null

  constructor() {
    this.setupPeerConnection()
  }

  private setupPeerConnection() {
    this.peerConnection = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    })

    // Set up audio track handler
    this.peerConnection.ontrack = (event) => {
      console.log('Received remote audio track')
      const [remoteStream] = event.streams
      this.events.onAudioTrack?.(remoteStream)
    }

    // Set up data channel for control messages
    this.peerConnection.ondatachannel = (event) => {
      this.dataChannel = event.channel
      this.dataChannel.onmessage = this.handleDataChannelMessage.bind(this)
    }

    // Connection state change handler
    this.peerConnection.onconnectionstatechange = () => {
      if (this.peerConnection) {
        const state = this.peerConnection.connectionState
        console.log('WebRTC connection state:', state)
        this.events.onConnectionStateChange?.(state)
        
        if (state === 'failed' || state === 'closed') {
          this.cleanup()
        }
      }
    }

    // ICE connection state handler
    this.peerConnection.oniceconnectionstatechange = () => {
      if (this.peerConnection) {
        console.log('ICE connection state:', this.peerConnection.iceConnectionState)
      }
    }
  }

  private handleDataChannelMessage(event: MessageEvent) {
    try {
      const message = JSON.parse(event.data)
      this.handleControlMessage(message)
    } catch (error) {
      console.error('Failed to parse data channel message:', error)
    }
  }

  private handleControlMessage(message: any) {
    switch (message.type) {
      case 'vad_update':
        this.events.onVADUpdate?.(message.energy, message.state)
        break
      case 'transcription':
        this.events.onTranscription?.(message.text)
        break
      case 'response':
        this.events.onResponse?.(message.text)
        break
      case 'status_update':
        this.events.onStatusUpdate?.(message.data)
        break
      case 'error':
        this.events.onError?.(message.message)
        break
      default:
        console.log('Unknown control message:', message)
    }
  }

  async connect(agentId?: string): Promise<void> {
    if (!this.peerConnection) {
      throw new Error('Peer connection not initialized')
    }

    try {
      // Get user media
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        }
      })

      // Add local audio track
      this.localStream.getAudioTracks().forEach(track => {
        this.peerConnection!.addTrack(track, this.localStream!)
      })

      // Create data channel for control messages
      this.dataChannel = this.peerConnection.createDataChannel('control')
      this.dataChannel.onmessage = this.handleDataChannelMessage.bind(this)

      // Create SDP offer
      const offer = await this.peerConnection.createOffer({
        offerToReceiveAudio: true,
        offerToReceiveVideo: false
      })

      await this.peerConnection.setLocalDescription(offer)

      // Send offer to backend
      const response = await fetch('http://localhost:8001/api/voicebot/webrtc/offer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sdp: offer.sdp,
          type: offer.type,
          agent_id: agentId || ''
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      this.sessionId = result.session_id

      // Set remote description
      const answer = new RTCSessionDescription({
        sdp: result.sdp,
        type: result.type
      })

      await this.peerConnection.setRemoteDescription(answer)

      console.log('WebRTC connection established with session ID:', this.sessionId)
    } catch (error) {
      console.error('Failed to connect WebRTC:', error)
      this.events.onError?.(error instanceof Error ? error.message : 'Connection failed')
      throw error
    }
  }

  disconnect(): void {
    this.cleanup()
    this.events.onConnectionStateChange?.('disconnected')
  }

  private cleanup() {
    // Stop local stream
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop())
      this.localStream = null
    }

    // Close data channel
    if (this.dataChannel) {
      this.dataChannel.close()
      this.dataChannel = null
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close()
      this.peerConnection = null
    }

    // Reinitialize for next connection
    setTimeout(() => {
      this.setupPeerConnection()
    }, 100)

    this.sessionId = null
  }

  // Event handlers
  set onConnectionStateChange(handler: (state: string) => void) {
    this.events.onConnectionStateChange = handler
  }

  set onAudioTrack(handler: (stream: MediaStream) => void) {
    this.events.onAudioTrack = handler
  }

  set onVADUpdate(handler: (energy: number, state: string) => void) {
    this.events.onVADUpdate = handler
  }

  set onTranscription(handler: (text: string) => void) {
    this.events.onTranscription = handler
  }

  set onResponse(handler: (text: string) => void) {
    this.events.onResponse = handler
  }

  set onStatusUpdate(handler: (status: any) => void) {
    this.events.onStatusUpdate = handler
  }

  set onError(handler: (error: string) => void) {
    this.events.onError = handler
  }

  // Utility methods
  isConnected(): boolean {
    return this.peerConnection?.connectionState === 'connected'
  }

  getConnectionState(): string {
    return this.peerConnection?.connectionState || 'disconnected'
  }

  getSessionId(): string | null {
    return this.sessionId
  }
}