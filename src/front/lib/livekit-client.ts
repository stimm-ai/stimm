'use client';

import {
  Room,
  RoomEvent,
  RemoteParticipant,
  LocalParticipant,
  RemoteTrackPublication,
  LocalTrackPublication,
} from 'livekit-client';
import { apiClient } from './frontend-config';

interface LiveKitEvents {
  onConnectionStateChange?: (state: string) => void;
  onAudioTrack?: (stream: MediaStream) => void;
  onLocalAudioTrack?: (stream: MediaStream) => void;
  onAgentJoined?: (participant: RemoteParticipant) => void;
  onAgentLeft?: (participant: RemoteParticipant) => void;
  onError?: (error: string) => void;
  onRoomConnected?: (room: Room) => void;
  onRoomDisconnected?: () => void;
  onDataReceived?: (
    payload: Uint8Array,
    participant?: RemoteParticipant
  ) => void;
}

export class LiveKitVoiceClient {
  private room: Room | null = null;
  private events: LiveKitEvents = {};
  private sessionId: string | null = null;
  private agentParticipant: RemoteParticipant | null = null;
  private localAudioPublication: LocalTrackPublication | null = null;
  private localStream: MediaStream | null = null;

  constructor() {
    // The new config logs itself, so this is just for confirmation
    console.log(
      'LiveKitVoiceClient initialized. LiveKit URL:',
      apiClient.getLiveKitUrl()
    );

    this.setupRoom();
  }

  private setupRoom() {
    this.room = new Room({
      // Configuration optimisée pour la voix
      adaptiveStream: true,
      dynacast: true,
    });

    // Événements de la salle
    this.room
      .on(RoomEvent.Connected, () => {
        console.log('✅ Connected to LiveKit room');
        this.events.onRoomConnected?.(this.room!);
        this.events.onConnectionStateChange?.('connected');
      })
      .on(RoomEvent.Disconnected, () => {
        console.log('❌ Disconnected from LiveKit room');
        this.events.onRoomDisconnected?.();
        this.events.onConnectionStateChange?.('disconnected');
        this.cleanup();
      })
      .on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
        console.log('👤 Participant connected:', participant.identity);

        // Vérifier si c'est l'agent (identité commence par "agent_")
        if (participant.identity.startsWith('agent_')) {
          this.agentParticipant = participant;
          this.events.onAgentJoined?.(participant);
          console.log('🤖 Agent joined the room');
        }
      })
      .on(
        RoomEvent.ParticipantDisconnected,
        (participant: RemoteParticipant) => {
          console.log('👤 Participant disconnected:', participant.identity);

          if (participant === this.agentParticipant) {
            this.agentParticipant = null;
            this.events.onAgentLeft?.(participant);
            console.log('🤖 Agent left the room');
          }
        }
      )
      .on(
        RoomEvent.TrackSubscribed,
        (track: any, publication: any, participant: RemoteParticipant) => {
          console.log(
            '🎵 Track subscribed:',
            track.kind,
            'from',
            participant.identity
          );

          if (track.kind === 'audio' && participant === this.agentParticipant) {
            // Créer un MediaStream avec la piste audio de l'agent
            const stream = new MediaStream([track.mediaStreamTrack]);
            this.events.onAudioTrack?.(stream);
            console.log('🔊 Agent audio track received');
          }
        }
      )
      .on(
        RoomEvent.TrackUnsubscribed,
        (track: any, publication: any, participant: RemoteParticipant) => {
          console.log(
            '🎵 Track unsubscribed:',
            track.kind,
            'from',
            participant.identity
          );
        }
      )
      .on(RoomEvent.ConnectionStateChanged, (state: string) => {
        console.log('🔗 Connection state changed:', state);
        this.events.onConnectionStateChange?.(state);
      })
      .on(RoomEvent.MediaDevicesError, (error: Error) => {
        console.error('🎤 Media devices error:', error);
        this.events.onError?.(error.message);
      })
      .on(
        RoomEvent.DataReceived,
        (
          payload: Uint8Array,
          participant?: RemoteParticipant,
          _kind?: any,
          _topic?: any
        ) => {
          //console.log('📦 Data received from:', participant?.identity)
          this.events.onDataReceived?.(payload, participant);
        }
      );
  }

  async connect(
    agentId: string,
    options?: { deviceId?: string }
  ): Promise<void> {
    if (!this.room) {
      throw new Error('Room not initialized');
    }

    try {
      // 1. Obtenir les informations de la salle depuis notre backend (environment-aware)
      const roomResponse = await apiClient.apiCall('/api/livekit/create-room', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agent_id: agentId,
        }),
      });

      if (!roomResponse.ok) {
        throw new Error(`Failed to create room: ${roomResponse.status}`);
      }

      const roomInfo = await roomResponse.json();
      this.sessionId = roomInfo.session_id;

      console.log('🎯 Connecting to LiveKit room:', roomInfo.room_name);

      // 2. Obtenir l'accès au microphone avec l'appareil sélectionné
      let localStream: MediaStream;
      try {
        const constraints: MediaStreamConstraints = {
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000,
            channelCount: 1,
            ...(options?.deviceId && { deviceId: { exact: options.deviceId } }),
          },
          video: false,
        };
        console.log(
          'Requesting microphone with deviceId:',
          options?.deviceId || 'default'
        );
        localStream = await navigator.mediaDevices.getUserMedia(constraints);
        const track = localStream.getAudioTracks()[0];
        console.log(
          'Acquired microphone:',
          track.label,
          'deviceId:',
          track.getSettings().deviceId
        );
      } catch (err: any) {
        // If exact device fails, try without deviceId
        if (
          err.name === 'NotFoundError' ||
          err.name === 'OverconstrainedError'
        ) {
          console.warn(
            `Device ${options?.deviceId} not available, falling back to default`
          );
          const fallbackConstraints: MediaStreamConstraints = {
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
              sampleRate: 16000,
              channelCount: 1,
            },
            video: false,
          };
          localStream =
            await navigator.mediaDevices.getUserMedia(fallbackConstraints);
          const track = localStream.getAudioTracks()[0];
          console.log(
            'Fell back to microphone:',
            track.label,
            'deviceId:',
            track.getSettings().deviceId
          );
        } else {
          throw err;
        }
      }

      // 3. Se connecter à la salle LiveKit (always use localhost for browser)
      const liveKitUrl = apiClient.getLiveKitUrl();
      await this.room.connect(liveKitUrl, roomInfo.access_token, {
        // Options de connexion
        autoSubscribe: true,
      });

      // Check for existing participants (if agent is already there)
      this.room.remoteParticipants.forEach((participant) => {
        if (participant.identity.startsWith('agent_')) {
          console.log('🤖 Found existing agent in room:', participant.identity);
          this.agentParticipant = participant;
          this.events.onAgentJoined?.(participant);

          // Check for existing tracks
          participant.trackPublications.forEach((publication) => {
            if (publication.track && publication.kind === 'audio') {
              // Manually trigger track handling
              const stream = new MediaStream([
                publication.track.mediaStreamTrack,
              ]);
              this.events.onAudioTrack?.(stream);
              console.log('🔊 Found existing agent audio track');
            }
          });
        }
      });

      // 4. Publier le microphone
      this.localStream = localStream;
      this.localAudioPublication =
        await this.room.localParticipant.publishTrack(
          localStream.getAudioTracks()[0],
          {
            name: 'microphone',
            // Optimisations pour la voix
            dtx: true, // Discontinuous Transmission
            red: true, // Redundancy
          }
        );

      console.log('✅ Successfully connected and published microphone');

      // Notify listeners about local audio track for visualization
      this.events.onLocalAudioTrack?.(localStream);
    } catch (error) {
      console.error('❌ Failed to connect to LiveKit:', error);
      this.events.onError?.(
        error instanceof Error ? error.message : 'Connection failed'
      );
      throw error;
    }
  }

  async switchMicrophone(deviceId?: string): Promise<void> {
    if (!this.room || this.room.state !== 'connected') {
      throw new Error('Not connected to a room');
    }
    if (!this.localAudioPublication) {
      throw new Error('No local audio track published');
    }

    let newStream: MediaStream;
    try {
      const constraints: MediaStreamConstraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1,
          ...(deviceId && { deviceId: { exact: deviceId } }),
        },
        video: false,
      };
      console.log('Switching microphone to deviceId:', deviceId || 'default');
      newStream = await navigator.mediaDevices.getUserMedia(constraints);
      const track = newStream.getAudioTracks()[0];
      console.log(
        'Switched to microphone:',
        track.label,
        'deviceId:',
        track.getSettings().deviceId
      );
    } catch (err: any) {
      // If exact device fails, try without deviceId
      if (err.name === 'NotFoundError' || err.name === 'OverconstrainedError') {
        console.warn(
          `Device ${deviceId} not available, falling back to default`
        );
        const fallbackConstraints: MediaStreamConstraints = {
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000,
            channelCount: 1,
          },
          video: false,
        };
        newStream =
          await navigator.mediaDevices.getUserMedia(fallbackConstraints);
        const track = newStream.getAudioTracks()[0];
        console.log(
          'Fell back to microphone:',
          track.label,
          'deviceId:',
          track.getSettings().deviceId
        );
      } else {
        throw err;
      }
    }

    // Unpublish old track
    const oldTrack = this.localAudioPublication.track;
    if (oldTrack) {
      this.room.localParticipant.unpublishTrack(oldTrack);
    }
    // Stop old stream
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
    }

    // Publish new track
    this.localStream = newStream;
    this.localAudioPublication = await this.room.localParticipant.publishTrack(
      newStream.getAudioTracks()[0],
      {
        name: 'microphone',
        dtx: true,
        red: true,
      }
    );

    // Notify listeners about new local audio track for visualization
    this.events.onLocalAudioTrack?.(newStream);

    console.log('✅ Successfully switched microphone');
  }

  async disconnect(): Promise<void> {
    if (this.room) {
      await this.room.disconnect();
    }
    this.cleanup();
  }

  private cleanup() {
    // Stop local stream tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
      this.localStream = null;
    }
    // Unpublish track if still published
    if (this.localAudioPublication && this.room?.localParticipant) {
      const track = this.localAudioPublication.track;
      if (track) {
        this.room.localParticipant.unpublishTrack(track);
      }
      this.localAudioPublication = null;
    }
    this.agentParticipant = null;
    this.sessionId = null;
  }

  // Méthodes utilitaires
  isConnected(): boolean {
    return this.room?.state === 'connected';
  }

  getConnectionState(): string {
    return this.room?.state || 'disconnected';
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  getAgentParticipant(): RemoteParticipant | null {
    return this.agentParticipant;
  }

  // Événements
  set onConnectionStateChange(handler: (state: string) => void) {
    this.events.onConnectionStateChange = handler;
  }

  set onAudioTrack(handler: (stream: MediaStream) => void) {
    this.events.onAudioTrack = handler;
  }

  set onLocalAudioTrack(handler: (stream: MediaStream) => void) {
    this.events.onLocalAudioTrack = handler;
  }

  set onAgentJoined(handler: (participant: RemoteParticipant) => void) {
    this.events.onAgentJoined = handler;
  }

  set onAgentLeft(handler: (participant: RemoteParticipant) => void) {
    this.events.onAgentLeft = handler;
  }

  set onError(handler: (error: string) => void) {
    this.events.onError = handler;
  }

  set onRoomConnected(handler: (room: Room) => void) {
    this.events.onRoomConnected = handler;
  }

  set onRoomDisconnected(handler: () => void) {
    this.events.onRoomDisconnected = handler;
  }

  set onDataReceived(
    handler: (payload: Uint8Array, participant?: RemoteParticipant) => void
  ) {
    this.events.onDataReceived = handler;
  }
}

// Export singleton pour une utilisation globale
export const liveKitClient = new LiveKitVoiceClient();
