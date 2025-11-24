import asyncio
import logging
import time
import fractions
import av
import numpy as np
from aiortc import MediaStreamTrack
from services.voicebot_wrapper.event_loop import VoicebotEventLoop

logger = logging.getLogger(__name__)

AUDIO_PTIME = 0.020  # 20ms audio packetization
AUDIO_RATE = 24000   # 24kHz sample rate (matches Kokoro TTS default)
AUDIO_CHANNELS = 1

class VoicebotAudioSender(MediaStreamTrack):
    """
    MediaStreamTrack that yields audio frames from the VoicebotEventLoop.
    """
    kind = "audio"

    def __init__(self, output_queue: asyncio.Queue):
        super().__init__()
        self.output_queue = output_queue
        self._timestamp = 0
        self._start_time = None
        self.packet_time = AUDIO_PTIME
        self.sample_rate = AUDIO_RATE
        self.samples_per_frame = int(self.sample_rate * self.packet_time)

    async def recv(self):
        """
        Called by aiortc to get the next audio frame.
        """
        if self._start_time is None:
            self._start_time = time.time()

        # Get audio data from the queue
        # The event loop puts {"type": "audio_chunk", "data": bytes}
        # We need to handle potential silence or waiting
        
        try:
            # Wait for audio data
            # We might need a more sophisticated buffering strategy here
            # to avoid gaps if the TTS is slightly slower than real-time
            # For now, we block until data is available.
            # In a real implementation, we might send silence if queue is empty
            # but we want to avoid drift.
            
            # Simple approach: Wait for data. 
            # If the queue is empty, aiortc will just wait (and silence might happen on client side)
            # or we can generate silence frames if we want to keep the clock ticking strictly.
            
            # Let's try to get data. If empty, maybe send silence?
            # But VoicebotEventLoop sends chunks as they are generated.
            
            # Ideally, we should have a buffer here.
            
            item = await self.output_queue.get()
            
            if item is None:
                # End of stream signal if we ever implement one
                self.stop()
                return None
                
            audio_bytes = item
            
            # Create AudioFrame
            # Assuming audio_bytes is raw PCM 16-bit
            # We need to ensure the chunk size matches what we expect (samples_per_frame)
            # If it doesn't, we might need to buffer/fragment.
            # For now, let's assume the TTS service produces chunks of appropriate size
            # or we handle arbitrary sizes.
            
            # Actually, av.AudioFrame.from_ndarray expects numpy array or similar
            # Let's convert bytes to AudioFrame
            
            # We need to know the format. 
            # Kokoro usually outputs 24kHz float32 or int16. 
            # Let's assume int16 for now as it's common.
            
            import numpy as np
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Reshape to (channels, samples)
            audio_array = audio_array.reshape(1, -1)
            
            frame = av.AudioFrame.from_ndarray(audio_array, format='s16', layout='mono')
            frame.sample_rate = self.sample_rate
            frame.pts = self._timestamp
            frame.time_base = fractions.Fraction(1, self.sample_rate)
            
            self._timestamp += frame.samples
            
            return frame
            
        except Exception as e:
            logger.error(f"Error in VoicebotAudioSender: {e}")
            raise

class WebRTCMediaHandler:
    """
    Manages the media tracks for a WebRTC session.
    """
    def __init__(self, event_loop: VoicebotEventLoop):
        self.event_loop = event_loop
        self.audio_sender = None
        self.audio_queue = asyncio.Queue() # Queue for outgoing audio frames (bytes)

    def add_outgoing_audio_track(self):
        """Creates and returns the outgoing audio track."""
        self.audio_sender = VoicebotAudioSender(self.audio_queue)
        return self.audio_sender

    async def handle_incoming_audio_track(self, track: MediaStreamTrack):
        """
        Consumes the incoming audio track and feeds it to the event loop.
        """
        logger.info("Started handling incoming audio track")
        try:
            while True:
                try:
                    frame = await track.recv()
                    
                    # Convert frame to bytes
                    # We want to standardize on 16kHz or 24kHz?
                    # The event loop expects raw bytes.
                    # Silero VAD expects 16kHz usually, or 8kHz.
                    # Let's resample if necessary or just pass it through if VAD handles it.
                    # Silero VAD supports 8k and 16k. 
                    # If the browser sends 48k (Opus default), we MUST resample.
                    
                    # Create resampler for 48kHz -> 16kHz with audio gain
                    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
                    resampled_frames = resampler.resample(frame)
                    
                    for resampled_frame in resampled_frames:
                        # Extract audio data
                        audio_array = resampled_frame.to_ndarray()
                        
                        # Apply audio gain to make VAD more sensitive
                        # Scale up the audio by factor of 3 to improve speech detection
                        audio_array = audio_array * 3
                        
                        # Ensure we don't clip (keep within int16 range)
                        audio_array = np.clip(audio_array, -32768, 32767)
                        
                        # Convert back to bytes
                        audio_bytes = audio_array.tobytes()
                        await self.event_loop.process_audio_chunk(audio_bytes)
                        
                except av.AudioError as e:
                    logger.warning(f"Audio error: {e}")
                    continue
        except asyncio.CancelledError:
            logger.info("Incoming audio track handler cancelled")
        except Exception as e:
            logger.error(f"Error handling incoming audio: {e}")
        finally:
            logger.info("Stopped handling incoming audio track")

    async def process_event_loop_output(self):
        """
        Reads from event_loop.output_queue and routes audio to audio_sender.
        """
        logger.info("Started processing event loop output")
        try:
            while True:
                event = await self.event_loop.output_queue.get()
                
                if event["type"] == "audio_chunk":
                    # This is audio for the user
                    data = event["data"]
                    if self.audio_sender:
                        await self.audio_queue.put(data)
                        
                # We can handle other events here if we want to send data channel messages
                # e.g. transcript updates
                
                self.event_loop.output_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Event loop output processor cancelled")
        except Exception as e:
            logger.error(f"Error processing event loop output: {e}")
