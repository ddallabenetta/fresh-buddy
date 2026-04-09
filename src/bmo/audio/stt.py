"""STT client — sends audio to the STT microservice over HTTP."""

import io
import logging
import queue
import threading
import wave
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ParakeetSTT:
    """Speech-to-text client backed by the STT microservice."""

    def __init__(self, config=None):
        self.config = config
        self._base_url = getattr(config, "stt_endpoint", "http://stt:5001").rstrip("/")
        self._sample_rate = 16000
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._transcription_thread: Optional[threading.Thread] = None
        self._audio_available: bool = self._check_audio()

    def _check_audio(self) -> bool:
        """Probe for a usable input device."""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            count = p.get_device_count()
            p.terminate()
            if count == 0:
                logger.warning("No audio devices found — STT running in silent mode")
                return False
            return True
        except ImportError:
            logger.warning("PyAudio not installed — STT running in silent mode")
            return False
        except Exception as e:
            logger.warning(f"Audio not available ({e}) — STT running in silent mode")
            return False

    def listen(self, timeout: float = 5.0) -> Optional[bytes]:
        """
        Capture audio from the microphone.

        Returns WAV bytes (16-bit PCM, 16 kHz, mono), or None if no mic.
        """
        if not self._audio_available:
            return None

        try:
            import pyaudio

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=1024,
            )

            logger.debug("Listening for audio...")
            frames = []
            chunk_count = int(self._sample_rate / 1024 * timeout)

            for _ in range(chunk_count):
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                except Exception:
                    break

            stream.stop_stream()
            stream.close()
            p.terminate()

            if frames:
                # Wrap raw PCM in a WAV container so the service can decode it
                buf = io.BytesIO()
                wf = wave.open(buf, "wb")
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._sample_rate)
                wf.writeframes(b"".join(frames))
                wf.close()
                audio_bytes = buf.getvalue()
                logger.debug(f"Captured {len(audio_bytes)} bytes of audio")
                return audio_bytes

        except Exception as e:
            logger.debug(f"Audio capture failed: {e}")

        return None

    def transcribe(self, audio_data: bytes) -> str:
        """Send audio WAV bytes to the STT service and return transcribed text."""
        if not audio_data:
            return ""

        try:
            resp = requests.post(
                f"{self._base_url}/transcribe",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                timeout=15,
            )
            resp.raise_for_status()
            text = resp.json().get("text", "")
            logger.info(f"Transcription: {text!r}")
            return text
        except Exception as e:
            logger.error(f"STT service error: {e}")
            return ""

    def start_streaming(self):
        """Start continuous listening mode."""
        if self._running:
            return
        self._running = True
        self._transcription_thread = threading.Thread(
            target=self._streaming_loop, daemon=True
        )
        self._transcription_thread.start()
        logger.info("STT streaming mode started")

    def stop(self):
        """Stop continuous listening."""
        self._running = False
        if self._transcription_thread:
            self._transcription_thread.join(timeout=2)
        logger.info("STT streaming stopped")

    def _streaming_loop(self):
        while self._running:
            try:
                audio_data = self.listen(timeout=3)
                if audio_data:
                    text = self.transcribe(audio_data)
                    if text.strip():
                        self._audio_queue.put(text)
            except Exception as e:
                logger.error(f"Streaming error: {e}")

    def get_transcription(self, timeout: float = 1.0) -> Optional[str]:
        """Get the next transcribed string from the queue."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_sample_rate(self, rate: int):
        self._sample_rate = rate

    @property
    def sample_rate(self) -> int:
        return self._sample_rate
