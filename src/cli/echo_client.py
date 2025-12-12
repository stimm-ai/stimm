#!/usr/bin/env python3
"""
LiveKit Echo Client - PyAudio Implementation
A robust, low-latency implementation using PyAudio (PortAudio).
"""

import asyncio
import logging
import threading
import time

import numpy as np
import pyaudio
from dotenv import load_dotenv
from livekit import rtc
from livekit.api import AccessToken, VideoGrants

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple-echo-client")

# Audio Configuration
SAMPLE_RATE = 48000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 960  # 20ms at 48kHz (matches LiveKit typical frame size)


class AudioEngine:
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._input_stream = None
        self._output_stream = None
        self._input_callback = None
        self._running = False
        self._loop = None

    def start(self, input_callback):
        self._input_callback = input_callback
        self._loop = asyncio.get_event_loop()
        self._running = True

        # Input Stream (Microphone)
        self._input_thread = threading.Thread(target=self._input_worker, daemon=True)
        self._input_thread.start()

        # Output Stream (Speaker)
        try:
            self._output_stream = self._pa.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, output=True, frames_per_buffer=CHUNK_SIZE)
            logger.info("🔊 Output stream started")
        except Exception as e:
            logger.error(f"Failed to open output stream: {e}")

    def stop(self):
        self._running = False
        if self._input_stream:
            self._input_stream.stop_stream()
            self._input_stream.close()
        if self._output_stream:
            self._output_stream.stop_stream()
            self._output_stream.close()
        self._pa.terminate()
        logger.info("Audio engine stopped")

    def _input_worker(self):
        logger.info("🎤 Input thread started")
        try:
            stream = self._pa.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE)
            self._input_stream = stream

            while self._running:
                try:
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    if self._loop and self._input_callback:
                        self._loop.call_soon_threadsafe(self._input_callback, data)
                except Exception as e:
                    logger.error(f"Input read error: {e}")
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to start input stream: {e}")

    def play_audio(self, data):
        if self._output_stream:
            try:
                # Blocking write - keeps sync
                self._output_stream.write(data)
            except Exception as e:
                logger.error(f"Output write error: {e}")


async def main():
    logger.info("🚀 Starting PyAudio echo client")

    # Audio Engine
    audio = AudioEngine()

    # Create LiveKit room
    room = rtc.Room()

    # Connect to LiveKit
    from environment_config import config

    url = config.livekit_url
    api_key = config.livekit_api_key
    api_secret = config.livekit_api_secret

    grants = VideoGrants(
        room_join=True,
        room="echo-test",
        can_publish=True,
        can_subscribe=True,
    )
    token = AccessToken(api_key=api_key, api_secret=api_secret).with_identity("test-client").with_name("Test Client").with_grants(grants).to_jwt()

    # Mic Source
    mic_source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=CHANNELS)
    mic_track = rtc.LocalAudioTrack.create_audio_track("mic", mic_source)

    def on_mic_data(data):
        # Called from input thread
        frame = rtc.AudioFrame.create(SAMPLE_RATE, CHANNELS, len(data) // 2)
        asyncio.ensure_future(push_mic_data(mic_source, frame, data))

    async def push_mic_data(source, frame, data):
        # Copy data
        frame_data_np = np.frombuffer(frame.data, dtype=np.int16)
        input_np = np.frombuffer(data, dtype=np.int16)
        np.copyto(frame_data_np, input_np)
        await source.capture_frame(frame)

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎧 Audio track subscribed: {participant.identity}")
            asyncio.create_task(handle_audio_track(track, audio))

    @room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected: {participant.identity}")
        if participant.identity == "echo-bot":
            # Subscribe to all audio tracks from echo agent
            for publication in participant.track_publications.values():
                if publication.kind == rtc.TrackKind.KIND_AUDIO:
                    publication.set_subscribed(True)
                    logger.info(f"✅ Subscribed to audio track from {participant.identity}")

    try:
        await room.connect(url, token)
        logger.info(f"✅ Connected to room {url}")

        await room.local_participant.publish_track(
            mic_track,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )

        # Start audio engine
        audio.start(on_mic_data)

        logger.info(" Echo client running! Speak and you should hear yourself!")

        # Keep alive
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        pass
    finally:
        audio.stop()
        await room.disconnect()


async def handle_audio_track(track, audio_engine):
    stream = rtc.AudioStream(track)
    async for event in stream:
        if event.frame:
            # Convert frame to bytes
            data = np.frombuffer(event.frame.data, dtype=np.int16).tobytes()
            # Push to audio engine (blocking write in executor)
            await asyncio.get_event_loop().run_in_executor(None, audio_engine.play_audio, data)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
