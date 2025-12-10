# Integration Examples

This section provides practical examples of integrating Stimm into your own applications using the recommended communication protocols.

## Development Testing

Before diving into integration examples, you may want to test your Stimm instance with a softphone. This is especially useful during development and validation.

### Testing with a Softphone

You can use a softphone (e.g., MicroSIP, Linphone, Zoiper) to call your Stimm instance directly if you have a public SIP server. This is useful for development and validation.

For production SIP integration, see the [SIP Integration for Deployed Instances](#sip-integration-for-deployed-instances) section below.

## WebRTC with LiveKit

Stimm uses [LiveKit](https://livekit.io/) as its real‑time audio engine. LiveKit provides a robust WebRTC stack that handles media streaming, signaling, and room management. To build a custom client that interacts with Stimm agents, you should connect directly to LiveKit via its client SDKs.

### Why WebRTC (not REST/WebSocket)?

- **Real‑time audio**: WebRTC is designed for low‑latency, high‑quality media streaming.
- **Built‑in signaling**: LiveKit manages the signaling channel, removing the need for custom WebSocket endpoints.
- **Scalability**: LiveKit rooms can scale horizontally and support many concurrent participants.
- **Cross‑platform**: LiveKit offers SDKs for web, mobile, and desktop.

### Example: Custom Web Client

You can create a custom web interface that connects to the same LiveKit room as an agent. The frontend included with Stimm (`src/front`) is a Next.js application that does exactly this – you can use it as a reference or build your own.

#### Steps

1. **Obtain a LiveKit token**
   Stimm’s backend provides an endpoint (`/api/livekit/create-room`) that creates a LiveKit room for a given agent and returns a token for the frontend to connect. You can call it from your client (no authentication required for local development) or generate tokens server‑side using the LiveKit API keys.

2. **Connect with the LiveKit JavaScript SDK**  
   Install `@livekit/client` and connect to the room:

   ```javascript
   import { Room, RoomEvent } from '@livekit/client';

   const room = new Room();
   await room.connect('wss://your-livekit-server', token);

   // Publish local microphone track
   const localTrack = await room.localParticipant.createAudioTrack();
   await room.localParticipant.publishTrack(localTrack);

   // Subscribe to remote tracks (the agent’s audio)
   room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
     if (track.kind === 'audio') {
       const audioElement = document.createElement('audio');
       audioElement.srcObject = new MediaStream([track.mediaStreamTrack]);
       audioElement.play();
     }
   });
   ```

3. **Handle agent events**  
   The agent will send data packets (e.g., transcription, intermediate results) over the data channel. You can listen for them:

   ```javascript
   room.on(RoomEvent.DataReceived, (payload, participant) => {
     const data = JSON.parse(payload);
     if (data.type === 'transcription') {
       console.log('Agent said:', data.text);
     }
   });
   ```

4. **Custom UI**  
   Build your own UI around the connection, displaying transcripts, controls, and agent status.

### Example: Mobile App (React Native)

LiveKit provides React Native SDKs (`@livekit/react-native`). The integration pattern is similar to the web.

## SIP Integration for Deployed Instances

If you have a deployed Stimm instance (e.g., on a public server) and want to connect it to a traditional telephony system, you can use the built‑in SIP bridge.

### How It Works

1. **Configure a SIP trunk**  
   In the Stimm admin interface (or via the REST API), create a SIP trunk that points to your SIP provider (e.g., Twilio, Asterisk).

2. **Set dispatch rules**  
   Define rules that map incoming SIP calls to specific Stimm agents. For example, you can route calls from a certain DID to an agent named “support”.

3. **Deploy the LiveKit SIP server**  
   Stimm includes a Docker service (`livekit‑sip`) that acts as a SIP‑to‑WebRTC gateway. It registers with your SIP provider and forwards media to LiveKit rooms.

### Example: Connecting to a Cloud PBX

Assume you have a cloud PBX that supports SIP trunking (e.g., FreePBX, 3CX). You would:

- Create a SIP trunk on the PBX pointing to your Stimm server’s SIP domain.
- In Stimm, create a corresponding trunk with the PBX’s IP/credentials.
- Define a dispatch rule that routes all incoming calls to the agent “reception”.

Once configured, any call made to the PBX extension will be forwarded to Stimm, and the assigned agent will answer.

### Testing SIP Connectivity

For development and validation, you can test your SIP configuration using a softphone (e.g., MicroSIP, Linphone, Zoiper). See the [Development Testing](#development-testing) section above for details.

## Using the REST API for Management

While real‑time audio should go through WebRTC, the REST API remains useful for **management tasks**:

- Creating/updating agents.
- Uploading documents to RAG.
- Retrieving conversation history.
- Monitoring system health.

## Next Steps

- Explore the [LiveKit documentation](https://docs.livekit.io/) for detailed SDK guides.
- Check the [SIP Integration](../user-guide/sip-integration.md) guide for step‑by‑step configuration.
- Look at the [Stimm frontend source](https://github.com/stimm-ai/stimm/tree/main/src/front) for a complete working example.