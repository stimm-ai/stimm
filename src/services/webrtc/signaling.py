import logging
import uuid
import asyncio
import json
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

# Make WebRTC imports optional
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
    WEBRTC_AVAILABLE = True
except ImportError as e:
    WEBRTC_AVAILABLE = False
    print(f"Warning: WebRTC dependencies not available: {e}")
    # Create dummy classes to avoid import errors
    class RTCPeerConnection:
        def __init__(self, *args, **kwargs): pass
        def addTrack(self, *args): pass
        def setRemoteDescription(self, *args): pass
        def setLocalDescription(self, *args): pass
        def createOffer(self, *args, **kwargs): pass
        def createAnswer(self, *args, **kwargs): pass
        def on(self, *args): pass
        
    class RTCSessionDescription:
        def __init__(self, sdp=None, type=None):
            self.sdp = sdp
            self.type = type

from services.webrtc.media_handler import WebRTCMediaHandler
from services.voicebot_wrapper.event_loop import VoicebotEventLoop
from services.vad.silero_service import SileroVADService
from services.stt.stt import STTService
from services.tts.tts import TTSService
from services.rag.chatbot_service import chatbot_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active connections
pcs = set()

class OfferRequest(BaseModel):
    sdp: str
    type: str
    agent_id: str = None

@router.post("/voicebot/webrtc/offer")
async def webrtc_offer(request: OfferRequest):
    """
    Handle WebRTC SDP offer.
    """
    offer = RTCSessionDescription(sdp=request.sdp, type=request.type)
    
    pc = RTCPeerConnection()
    pcs.add(pc)
    
    # Create session ID
    session_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    
    logger.info(f"Starting WebRTC session: {session_id}")
    
    # Initialize services - use agent_id or default to a valid agent
    agent_id = request.agent_id if request.agent_id and request.agent_id != 'default' else '0d6e6332-384a-45e7-bd75-842fe6b3149e'  # Default agent ID from logs
    
    # Initialize services
    vad_service = SileroVADService()
    stt_service = STTService(agent_id=agent_id, session_id=session_id)
    tts_service = TTSService(agent_id=agent_id, session_id=session_id)
    
    # Initialize Event Loop
    # We need an output queue for the event loop to push audio/events to
    output_queue = asyncio.Queue()
    
    event_loop = VoicebotEventLoop(
        conversation_id=conversation_id,
        output_queue=output_queue,
        stt_service=stt_service,
        chatbot_service=chatbot_service,
        tts_service=tts_service,
        vad_service=vad_service,
        agent_id=agent_id,
        session_id=session_id
    )
    
    # Initialize Media Handler
    media_handler = WebRTCMediaHandler(event_loop)
    
    # Add outgoing audio track (TTS)
    audio_sender = media_handler.add_outgoing_audio_track()
    pc.addTrack(audio_sender)
    
    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            # Handle control messages if any
            pass
            
    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            logger.info("Received audio track")
            # Handle incoming audio
            asyncio.create_task(media_handler.handle_incoming_audio_track(track))
            
        @track.on("ended")
        async def on_ended():
            logger.info("Track ended")
            
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await cleanup()

    async def cleanup():
        logger.info(f"Cleaning up session {session_id}")
        await event_loop.stop()
        pcs.discard(pc)
        # Close PC if not already closed
        if pc.connectionState != "closed":
            await pc.close()

    # Start Event Loop
    await event_loop.start()
    
    # Start processing event loop output to feed audio sender
    asyncio.create_task(media_handler.process_event_loop_output())

    # Handle SDP
    await pc.setRemoteDescription(offer)
    
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
        "session_id": session_id
    }

@router.on_event("shutdown")
async def on_shutdown():
    # Close all connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
