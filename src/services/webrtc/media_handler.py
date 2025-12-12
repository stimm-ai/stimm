import asyncio
import fractions
import logging
import time

import av
from aiortc import MediaStreamTrack

from services.agents.event_loop import StimmEventLoop

logger = logging.getLogger(__name__)

AUDIO_PTIME = 0.020  # 20ms audio packetization
AUDIO_RATE = 24000  # 24kHz sample rate (matches Kokoro TTS default)
AUDIO_CHANNELS = 1


class StimmAudioSender(MediaStreamTrack):
    """
    MediaStreamTrack that yields audio frames from the StimmEventLoop.
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

        # Internal buffer for packetization
        self.internal_buffer = bytearray()
        self.bytes_per_sample = 2  # 16-bit
        self.bytes_per_frame = self.samples_per_frame * self.bytes_per_sample

    def set_sample_rate(self, sample_rate: int):
        """Update the sample rate and recalculate frame size."""
        if self.sample_rate != sample_rate:
            logger.info(f"🔄 Updating VoicebotAudioSender sample rate: {self.sample_rate} -> {sample_rate} Hz")
            self.sample_rate = sample_rate
            self.samples_per_frame = int(self.sample_rate * self.packet_time)
            self.bytes_per_frame = self.samples_per_frame * self.bytes_per_sample
            # Note: Existing buffer content assumes old sample rate, but since it's raw bytes,
            # we can't easily convert it. We just continue processing with new frame size.
            # This might cause a glitch at transition, but it's better than wrong rate.

    def flush(self):
        """Clear the internal audio buffer."""
        self.internal_buffer.clear()
        logger.info("🗑️ VoicebotAudioSender buffer flushed")

    async def recv(self):
        """
        Called by aiortc to get the next audio frame.
        Handles packetization of large chunks into 20ms frames.
        Includes pacing to prevent buffering too far ahead in the network stack.
        """
        if self._start_time is None:
            self._start_time = time.time()

        # Pacing: Wait if we are too far ahead of real-time
        # current_pts_time is when this frame should play relative to start
        current_pts_time = self._timestamp / self.sample_rate
        # real_time_elapsed is how long we've been playing
        real_time_elapsed = time.time() - self._start_time

        # We allow buffering ahead by a small margin (e.g. 200ms)
        # to prevent underruns while keeping latency low for interruption.
        buffer_margin = 0.2

        wait_time = current_pts_time - real_time_elapsed - buffer_margin
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        try:
            # We need enough bytes for one frame
            while len(self.internal_buffer) < self.bytes_per_frame:
                try:
                    # Try to get more data
                    # If we have some data but not enough, we wait
                    # If we have no data, we wait
                    item = await self.output_queue.get()

                    if item is None:
                        # End of stream signal
                        if len(self.internal_buffer) == 0:
                            self.stop()
                            return None
                        else:
                            # We have leftover bytes, pad with silence?
                            # Or just return what we have (might cause artifact)
                            # Let's pad with silence to full frame size
                            padding = self.bytes_per_frame - len(self.internal_buffer)
                            self.internal_buffer.extend(b"\x00" * padding)
                            break

                    self.internal_buffer.extend(item)

                except Exception as e:
                    logger.error(f"Error getting audio from queue: {e}")
                    raise

            # Extract one frame worth of bytes
            frame_bytes = self.internal_buffer[: self.bytes_per_frame]
            del self.internal_buffer[: self.bytes_per_frame]

            # Convert to AudioFrame
            import numpy as np

            audio_array = np.frombuffer(frame_bytes, dtype=np.int16)

            # Reshape to (channels, samples)
            audio_array = audio_array.reshape(1, -1)

            frame = av.AudioFrame.from_ndarray(audio_array, format="s16", layout="mono")
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

    def __init__(self, event_loop: StimmEventLoop):
        self.event_loop = event_loop
        self.audio_sender = None
        self.audio_queue = asyncio.Queue()  # Queue for outgoing audio frames (bytes)
        self.data_channel = None  # Data channel for control messages
        self.pc = None  # Peer connection reference

    def set_data_channel(self, channel):
        """Set the data channel for control messages"""
        self.data_channel = channel

    def set_peer_connection(self, pc):
        """Set the peer connection reference"""
        self.pc = pc

    async def send_control_message(self, message_type: str, data: dict):
        """Send a control message via data channel"""
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                import json

                message = {"type": message_type, **data}
                self.data_channel.send(json.dumps(message))
                logger.debug(f"📡 Sent data channel message: {message_type}")
            except Exception as e:
                logger.error(f"Failed to send data channel message: {e}")
        else:
            logger.warning("Data channel not ready for control messages")

    def add_outgoing_audio_track(self):
        """Creates and returns the outgoing audio track."""
        self.audio_sender = StimmAudioSender(self.audio_queue)
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
                    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
                    resampled_frames = resampler.resample(frame)

                    for resampled_frame in resampled_frames:
                        # Extract audio data
                        audio_array = resampled_frame.to_ndarray()

                        # Removed artificial gain (was * 3) to prevent false positive interruptions.
                        # VAD sensitivity should be managed via VAD thresholds, not digital gain
                        # which amplifies noise and causes clipping.

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
        Reads from event_loop.output_queue and routes events appropriately.
        """
        logger.info("📡 Started processing event loop output")
        try:
            while True:
                event = await self.event_loop.output_queue.get()
                event_type = event.get("type", "unknown")

                # Route events based on type
                if event_type == "audio_chunk":
                    # This is audio for the user
                    data = event["data"]
                    if self.audio_sender:
                        await self.audio_queue.put(data)
                        # logger.debug(f"🎵 Sent audio chunk to sender: {len(data)} bytes")

                elif event_type == "interrupt":
                    # Handle interruption: Clear audio queue immediately
                    logger.info("🛑 Interruption signal received in media handler - Flushing audio queue")

                    # Drain the audio queue
                    dropped_chunks = 0
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                            dropped_chunks += 1
                        except asyncio.QueueEmpty:
                            break

                    logger.info(f"🗑️ Flushed {dropped_chunks} audio chunks from queue")

                    # Also flush the sender's internal buffer (crucial for large chunks)
                    if self.audio_sender:
                        self.audio_sender.flush()

                elif event_type == "vad_update":
                    # Send VAD status to client via data channel
                    await self.send_control_message("vad_update", {"energy": event.get("energy", 0), "state": event.get("state", "silence")})
                    logger.debug(f"👁️ Sent VAD update: {event.get('state')} (energy: {event.get('energy', 0):.2f})")

                elif event_type == "transcript_update":
                    # Send transcript to client via data channel
                    await self.send_control_message("transcription", {"text": event.get("text", ""), "is_final": event.get("is_final", False)})
                    logger.debug(f"📝 Sent transcript: '{event.get('text', '')[:50]}...' (final: {event.get('is_final', False)})")

                elif event_type == "assistant_response":
                    # Send assistant response to client via data channel
                    await self.send_control_message("response", {"text": event.get("text", ""), "is_complete": event.get("is_complete", False)})
                    logger.debug(f"🤖 Sent response: '{event.get('text', '')[:50]}...' (complete: {event.get('is_complete', False)})")

                elif event_type == "speech_start":
                    await self.send_control_message("speech_start", {})
                    logger.debug("🗣️ Speech start")

                elif event_type == "speech_end":
                    await self.send_control_message("speech_end", {})
                    logger.debug("🤫 Speech end")

                elif event_type == "bot_responding_start":
                    await self.send_control_message("status_update", {"state": "responding"})
                    logger.debug("🤖 Bot responding start")

                elif event_type == "bot_responding_end":
                    await self.send_control_message("status_update", {"state": "listening"})
                    logger.debug("🤖 Bot responding end")

                elif event_type == "error":
                    # Send error to client via data channel
                    await self.send_control_message("error", event.get("data", {}))
                    logger.error(f"❌ Sent error: {event.get('data', {})}")

                else:
                    logger.warning(f"⚠️ Unknown event type: {event_type}")

                self.event_loop.output_queue.task_done()

        except asyncio.CancelledError:
            logger.info("Event loop output processor cancelled")
        except Exception as e:
            logger.error(f"Error processing event loop output: {e}")
