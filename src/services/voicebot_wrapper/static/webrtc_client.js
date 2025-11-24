/**
 * WebRTC Client for Voicebot
 * Handles microphone capture, SDP negotiation, and audio playback.
 */

class WebRTCClient {
    constructor(config = {}) {
        this.config = {
            url: '/api/voicebot/webrtc/offer',
            ...config
        };

        this.pc = null;
        this.localStream = null;
        this.remoteStream = new MediaStream();
        this.onConnectionStateChange = null;
        this.onAudioTrack = null;
    }

    async start(agentId = null) {
        console.log('Starting WebRTC session...');

        // 1. Get Microphone Access
        try {
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                },
                video: false
            });
        } catch (err) {
            console.error('Failed to get user media:', err);
            throw err;
        }

        // 2. Create Peer Connection
        this.pc = new RTCPeerConnection({
            sdpSemantics: 'unified-plan'
        });

        // 3. Add Local Tracks
        this.localStream.getTracks().forEach(track => {
            this.pc.addTrack(track, this.localStream);
        });

        // 4. Handle Remote Tracks
        this.pc.ontrack = (event) => {
            console.log('Received remote track:', event.track.kind);
            if (event.track.kind === 'audio') {
                this.remoteStream.addTrack(event.track);
                if (this.onAudioTrack) {
                    this.onAudioTrack(this.remoteStream);
                }
            }
        };

        this.pc.onconnectionstatechange = () => {
            console.log('Connection state:', this.pc.connectionState);
            if (this.onConnectionStateChange) {
                this.onConnectionStateChange(this.pc.connectionState);
            }
        };

        // 5. Create Offer
        const offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);

        // 6. Send Offer to Backend
        // Wait for ICE gathering to complete (optional but good for stability)
        await new Promise((resolve) => {
            if (this.pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    if (this.pc.iceGatheringState === 'complete') {
                        this.pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                };
                this.pc.addEventListener('icegatheringstatechange', checkState);
                // Fallback timeout
                setTimeout(resolve, 1000);
            }
        });

        const response = await fetch(this.config.url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sdp: this.pc.localDescription.sdp,
                type: this.pc.localDescription.type,
                agent_id: agentId
            })
        });

        if (!response.ok) {
            throw new Error(`Signaling failed: ${response.statusText}`);
        }

        const answer = await response.json();

        // 7. Set Remote Description
        await this.pc.setRemoteDescription(answer);

        console.log('WebRTC session established');
        return answer.session_id;
    }

    stop() {
        console.log('Stopping WebRTC session...');
        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }
    }
}

// Export global
window.WebRTCClient = WebRTCClient;
