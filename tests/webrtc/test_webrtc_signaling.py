import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from aiortc import RTCPeerConnection, RTCSessionDescription

# Import app
from main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_webrtc_offer():
    """
    Test the /voicebot/webrtc/offer endpoint.
    """
    # Create a local PC to generate an offer
    pc = RTCPeerConnection()
    pc.addTransceiver("audio", direction="sendrecv")
    
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    # Send offer to backend
    response = client.post(
        "/api/voicebot/webrtc/offer",
        json={
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "agent_id": "default"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "sdp" in data
    assert "type" in data
    assert data["type"] == "answer"
    assert "session_id" in data
    
    # Set remote description
    answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    await pc.setRemoteDescription(answer)
    
    # Cleanup
    await pc.close()
