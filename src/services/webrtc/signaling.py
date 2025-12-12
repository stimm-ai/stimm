import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Make WebRTC imports optional
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription

    WEBRTC_AVAILABLE = True
except ImportError as e:
    WEBRTC_AVAILABLE = False
    print(f"Warning: WebRTC dependencies not available: {e}")

    # Create dummy classes to avoid import errors
    class RTCPeerConnection:
        def __init__(self, *args, **kwargs):
            pass

        def addTrack(self, *args):
            pass

        def setRemoteDescription(self, *args):
            pass

        def setLocalDescription(self, *args):
            pass

        def createOffer(self, *args, **kwargs):
            pass

        def createAnswer(self, *args, **kwargs):
            pass

        def on(self, *args):
            pass

    class RTCSessionDescription:
        def __init__(self, sdp=None, type=None):
            self.sdp = sdp
            self.type = type


from services.agents.event_loop import StimmEventLoop
from services.rag.chatbot_service import chatbot_service
from services.stt.stt import STTService
from services.tts.tts import TTSService
from services.vad.silero_service import SileroVADService
from services.webrtc.media_handler import WebRTCMediaHandler

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active connections
pcs = set()


class OfferRequest(BaseModel):
    sdp: str
    type: str
    agent_id: str = None


@router.post("/stimm/webrtc/offer")
async def webrtc_offer(request: OfferRequest):
    """
    Handle WebRTC SDP offer.
    """
    logger.info(f"🌐 Received WebRTC offer from agent: {request.agent_id}")

    offer = RTCSessionDescription(sdp=request.sdp, type=request.type)

    pc = RTCPeerConnection()
    pcs.add(pc)

    # Create session ID
    session_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    logger.info(f"🔗 Starting WebRTC session: {session_id}")

    # Initialize services - use agent_id or fallback to a valid agent
    agent_id = request.agent_id if request.agent_id and request.agent_id != "default" else None

    try:
        # CRITICAL FIX: Ensure we have a valid agent_id
        if not agent_id:
            try:
                from services.agents_admin.agent_manager import get_agent_manager

                agent_manager = get_agent_manager()
                agents = agent_manager.list_agents()
                if agents:
                    agent_id = str(agents[0].id)  # Use first available agent
                    logger.info(f"🔧 Using default agent: {agent_id} ({agents[0].name})")
                else:
                    logger.error("❌ No agents available in the system")
                    raise HTTPException(status_code=500, detail="No agents configured")
            except Exception as e:
                logger.error(f"❌ Failed to get agent: {e}")
                raise HTTPException(status_code=500, detail=f"Agent configuration error: {str(e)}")

        # Initialize services with error handling
        logger.info(f"🔧 Initializing services for agent: {agent_id}")

        vad_service = SileroVADService()
        stt_service = STTService(agent_id=agent_id, session_id=session_id)
        tts_service = TTSService(agent_id=agent_id, session_id=session_id)

        logger.info("✅ Services initialized:")
        logger.info(f"   - VAD: {vad_service.__class__.__name__}")
        logger.info(f"   - STT: {stt_service.provider.__class__.__name__ if stt_service.provider else 'None'}")
        logger.info(f"   - TTS: {tts_service.provider.__class__.__name__ if tts_service.provider else 'None'}")

        # Initialize Event Loop
        output_queue = asyncio.Queue()

        event_loop = StimmEventLoop(
            conversation_id=conversation_id,
            output_queue=output_queue,
            stt_service=stt_service,
            chatbot_service=chatbot_service,
            tts_service=tts_service,
            vad_service=vad_service,
            agent_id=agent_id,
            session_id=session_id,
        )

        # Initialize Media Handler
        media_handler = WebRTCMediaHandler(event_loop)

        # Store references in media_handler
        media_handler.set_peer_connection(pc)

        # Add outgoing audio track (TTS)
        audio_sender = media_handler.add_outgoing_audio_track()
        pc.addTrack(audio_sender)

        @pc.on("datachannel")
        def on_datachannel(channel):
            logger.info(f"📡 Data channel opened: {channel.label}")
            # Store data channel reference
            media_handler.set_data_channel(channel)

            @channel.on("message")
            def on_message(message):
                logger.debug(f"📨 Received data channel message: {message}")
                # Handle control messages if any
                pass

            @channel.on("close")
            def on_close():
                logger.info("📡 Data channel closed")
                media_handler.data_channel = None

        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                logger.info("🎤 Received audio track")
                # Handle incoming audio
                asyncio.create_task(media_handler.handle_incoming_audio_track(track))

            @track.on("ended")
            async def on_ended():
                logger.info("🎤 Audio track ended")

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = pc.connectionState
            logger.info(f"🔗 Connection state: {state}")

            if state == "connected":
                logger.info("✅ WebRTC connection established successfully!")
                # Send welcome message
                await media_handler.send_control_message("status_update", {"connected": True, "session_id": session_id})

            elif state in ["failed", "closed", "disconnected"]:
                logger.warning(f"❌ WebRTC connection {state}")
                await cleanup()

        async def cleanup():
            logger.info(f"🧹 Cleaning up session {session_id}")
            try:
                await event_loop.stop()
            except Exception as e:
                logger.error(f"Error stopping event loop: {e}")
            pcs.discard(pc)
            # Close PC if not already closed
            if pc.connectionState != "closed":
                try:
                    await pc.close()
                except Exception as e:
                    logger.error(f"Error closing PC: {e}")

        # Start Event Loop
        logger.info("🚀 Starting Event Loop")
        await event_loop.start()

        # Start processing event loop output to feed audio sender
        logger.info("📡 Starting event loop output processor")
        asyncio.create_task(media_handler.process_event_loop_output())

        # Handle SDP
        logger.info("🤝 Processing SDP offer/answer")
        await pc.setRemoteDescription(offer)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        logger.info(f"✅ WebRTC setup completed for session {session_id}")

        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "session_id": session_id}

    except Exception as e:
        logger.error(f"❌ WebRTC setup failed: {e}")
        # Cleanup on failure
        try:
            await pc.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"WebRTC setup failed: {str(e)}")


@router.on_event("shutdown")
async def on_shutdown():
    # Close all connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
