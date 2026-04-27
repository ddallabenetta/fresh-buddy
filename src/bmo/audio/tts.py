"""TTS client — sends text to the TTS microservice over HTTP."""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

try:
    import pyaudio
except ImportError:
    pyaudio = None


class PiperTTS:
    """Text-to-speech client backed by the TTS microservice."""

    def __init__(self, config=None):
        self.config = config
        self._base_url = getattr(config, "tts_endpoint", "http://tts:5002").rstrip("/")
        self.voice = getattr(config, "piper_voice", "en_US-lessac-medium")
        self._speaker_id = getattr(config, "piper_speaker", None)
        self._noise_scale = getattr(config, "piper_noise_scale", 0.667)
        self._length_scale = getattr(config, "piper_length_scale", 1.0)
        self._audio_available: bool = self._check_audio()

    def _check_audio(self) -> bool:
        """Probe for a usable output device."""
        if pyaudio is None:
            logger.warning("PyAudio not installed — TTS playback disabled")
            return False
        try:
            p = pyaudio.PyAudio()
            count = p.get_device_count()
            p.terminate()
            if count == 0:
                logger.warning("No audio devices found — TTS playback disabled")
                return False
            return True
        except Exception as e:
            logger.warning(f"Audio not available ({e}) — TTS playback disabled")
            return False

    def speak(self, text: str, blocking: bool = True) -> Optional[bytes]:
        """
        Synthesize text via the TTS service and play it locally.

        Returns WAV bytes, or None on failure.
        """
        if not text:
            return None

        logger.info(f"Synthesizing: {text[:50]}...")

        try:
            resp = requests.post(
                f"{self._base_url}/synthesize",
                json={"text": text},
                timeout=30,
            )
            resp.raise_for_status()
            audio_data = resp.content

            if blocking:
                self._play_audio(audio_data)

            return audio_data

        except Exception as e:
            logger.error(f"TTS service error: {e}")
            return None

    def _play_audio(self, audio_data: bytes):
        """Play WAV bytes through local speakers (no-op if no audio device)."""
        if not self._audio_available:
            return

        try:
            import wave

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                wav_file = f.name

            wf = wave.open(wav_file, "rb")
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )

            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)

            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            Path(wav_file).unlink(missing_ok=True)

        except Exception as e:
            logger.debug(f"Audio playback failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str):
        """Synthesize text and save the WAV to a file."""
        audio_data = self.speak(text, blocking=False)
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            logger.info(f"Audio saved to {output_path}")

    def set_voice(self, voice: str):
        self.voice = voice
        logger.info(f"Voice change to '{voice}' requires TTS service restart")

    def set_speaker(self, speaker_id: int):
        self._speaker_id = speaker_id
        logger.info("Speaker change requires TTS service restart")

    def cleanup(self):
        logger.info("PiperTTS client cleanup complete")

    @staticmethod
    def download_voice(voice_name: str, destination: str = "."):
        logger.info("Voice download is handled by the TTS service container")
