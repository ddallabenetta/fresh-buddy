"""Parakeet STT (Speech-to-Text) Module"""

import logging
import threading
import queue
from typing import Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ParakeetSTT:
    """Parakeet speech-to-text using Coqui/STT models."""

    def __init__(self, config=None):
        """
        Initialize Parakeet STT.

        Args:
            config: Configuration object
        """
        self.config = config
        self.model = None
        self._sample_rate = 16000
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._transcription_thread: Optional[threading.Thread] = None

        self._init_model()

    def _init_model(self):
        """Initialize Parakeet model."""
        model_path = getattr(self.config, 'parakeet_model_path', None)

        try:
            # Try to import coqui-stt
            from coei_stt import Model

            if model_path and Path(model_path).exists():
                logger.info(f"Loading Parakeet model from {model_path}")
                self.model = Model(str(model_path))
            else:
                # Try to use Parakeet directly
                logger.info("Initializing Parakeet with default settings")
                # Default to tap-8k for Jetson optimization
                self.model = Model()

            logger.info("Parakeet STT model loaded successfully")

        except ImportError:
            logger.warning("Coqui STT not available, using mock mode")
            logger.info("Install with: pip install coqui-stt")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load Parakeet model: {e}")
            self.model = None

    def listen(self, timeout: float = 5.0) -> Optional[bytes]:
        """
        Listen for audio input.

        Args:
            timeout: Maximum time to listen in seconds

        Returns:
            Audio data as bytes (16-bit PCM at 16kHz) or None if timeout
        """
        audio_data = None

        try:
            import pyaudio

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=1024
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
                audio_data = b''.join(frames)
                logger.debug(f"Captured {len(audio_data)} bytes of audio")

        except ImportError:
            logger.warning("PyAudio not available")
        except Exception as e:
            logger.error(f"Error capturing audio: {e}")

        return audio_data

    def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Audio bytes (16-bit PCM at 16kHz)

        Returns:
            Transcribed text
        """
        if not audio_data:
            return ""

        if self.model is None:
            # Mock transcription for testing
            logger.info("Mock transcription (no model loaded)")
            return "Mock transcription - install coqui-stt for real use"

        try:
            # Convert bytes to numpy array
            import numpy as np

            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0

            # Run inference
            text = self.model.stt(audio_float)
            logger.info(f"Transcription: {text}")

            return text

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def start_streaming(self):
        """Start continuous listening mode."""
        if self._running:
            return

        self._running = True
        self._transcription_thread = threading.Thread(
            target=self._streaming_loop,
            daemon=True
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
        """Continuous streaming transcription loop."""
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
        """
        Get transcribed text from queue.

        Args:
            timeout: How long to wait for text

        Returns:
            Transcribed text or None
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_sample_rate(self, rate: int):
        """Set audio sample rate."""
        self._sample_rate = rate

    @property
    def sample_rate(self) -> int:
        """Get current sample rate."""
        return self._sample_rate
