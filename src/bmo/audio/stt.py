"""STT client — sends audio to the STT microservice over HTTP."""

import io
import logging
import queue
import threading
import time
import wave
from typing import Optional

import requests

logger = logging.getLogger(__name__)

try:
    import pyaudio
except ImportError:
    pyaudio = None


class ParakeetSTT:
    """Speech-to-text client backed by the STT microservice."""

    def __init__(self, config=None):
        self.config = config
        self._base_url = getattr(config, "stt_endpoint", "http://stt:5001").rstrip("/")
        self._sample_rate = 16000
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._transcription_thread: Optional[threading.Thread] = None
        self._input_device_index: Optional[int] = None
        self._audio_available: bool = self._check_audio()

    @staticmethod
    def _normalize_device_hint(value):
        if value in (None, "", "auto"):
            return None
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value

    def _resolve_input_device(self, p) -> Optional[int]:
        configured = self._normalize_device_hint(
            getattr(self.config, "audio_input_device", None)
        )
        fallback = self._normalize_device_hint(getattr(self.config, "audio_device", None))
        preferred = configured if configured is not None else fallback

        devices = []
        for idx in range(p.get_device_count()):
            info = p.get_device_info_by_index(idx)
            if int(info.get("maxInputChannels", 0)) > 0:
                devices.append((idx, info))

        if not devices:
            return None

        if isinstance(preferred, int):
            for idx, info in devices:
                if idx == preferred:
                    logger.info(
                        "Using configured input device %s: %s",
                        idx,
                        info.get("name", "unknown"),
                    )
                    return idx
            logger.warning("Configured input device index %s not found", preferred)

        if isinstance(preferred, str):
            preferred_lower = preferred.lower()
            for idx, info in devices:
                name = info.get("name", "").lower()
                if preferred_lower in name:
                    logger.info(
                        "Using configured input device %s: %s",
                        idx,
                        info.get("name", "unknown"),
                    )
                    return idx
            logger.warning("Configured input device '%s' not found", preferred)

        keywords = ("respeaker", "seeed", "usb", "mic", "microphone")
        for idx, info in devices:
            name = info.get("name", "").lower()
            if any(keyword in name for keyword in keywords):
                logger.info(
                    "Auto-selected input device %s: %s",
                    idx,
                    info.get("name", "unknown"),
                )
                return idx

        idx, info = devices[0]
        logger.info("Using default input device %s: %s", idx, info.get("name", "unknown"))
        return idx

    def _check_audio(self) -> bool:
        """Probe for a usable input device."""
        if pyaudio is None:
            logger.warning("PyAudio not installed — STT running in silent mode")
            return False
        try:
            p = pyaudio.PyAudio()
            self._input_device_index = self._resolve_input_device(p)
            count = p.get_device_count()
            p.terminate()
            if count == 0:
                logger.warning("No audio devices found — STT running in silent mode")
                return False
            if self._input_device_index is None:
                logger.warning("No usable capture device found — STT running in silent mode")
                return False
            return True
        except Exception as e:
            logger.warning(f"Audio not available ({e}) — STT running in silent mode")
            return False

    def listen(self, timeout: float = 5.0) -> Optional[bytes]:
        """
        Capture audio from the microphone.

        Returns WAV bytes (16-bit PCM, 16 kHz, mono), or None if no mic.
        """
        if not self._audio_available:
            time.sleep(0.5)
            return None

        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._sample_rate,
                input=True,
                input_device_index=self._input_device_index,
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
