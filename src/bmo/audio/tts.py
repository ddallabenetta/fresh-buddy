"""Piper TTS (Text-to-Speech) Module"""

import logging
import subprocess
import tempfile
import struct
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PiperTTS:
    """Piper text-to-speech synthesis."""

    def __init__(self, config=None):
        """
        Initialize Piper TTS.

        Args:
            config: Configuration object
        """
        self.config = config
        self.model_path = getattr(self.config, 'piper_model_path', None)
        self.voice = getattr(self.config, 'piper_voice', 'en_US-lessac-medium')
        self._speaker_id = getattr(self.config, 'piper_speaker', None)
        self._noise_scale = getattr(self.config, 'piper_noise_scale', 0.667)
        self._length_scale = getattr(self.config, 'piper_length_scale', 1.0)
        self._session = None

        self._check_installation()

    def _check_installation(self):
        """Check if Piper is installed."""
        try:
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"Piper installed: {result.stdout.strip()}")
            else:
                logger.warning("Piper not found in PATH")
                logger.info("Install: pip install piper-tts && piper-download en_US-lessac-medium")
        except FileNotFoundError:
            logger.warning("Piper executable not found")
            logger.info("Install: pip install piper-tts && piper-download en_US-lessac-medium")
        except Exception as e:
            logger.error(f"Error checking Piper: {e}")

    def speak(self, text: str, blocking: bool = True) -> Optional[bytes]:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            blocking: Wait for completion before returning

        Returns:
            Audio data as WAV bytes, or None if failed
        """
        if not text:
            return None

        logger.info(f"Synthesizing: {text[:50]}...")

        try:
            # Create input file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(text)
                input_file = f.name

            # Create output file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                output_file = f.name

            # Build piper command
            cmd = ["piper"]
            cmd.extend(["--model", self._get_model_flag()])
            cmd.extend(["--output-raw" if not blocking else "--output-file", output_file if blocking else "-"])
            cmd.extend(["--speaker", str(self._speaker_id)]) if self._speaker_id else None
            cmd.extend(["--noise-scale", str(self._noise_scale)])
            cmd.extend(["--length-scale", str(self._length_scale)])
            cmd.append(input_file)

            # Remove None values
            cmd = [c for c in cmd if c is not None]

            logger.debug(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Piper error: {result.stderr}")
                return None

            if blocking:
                # Read output file
                with open(output_file, 'rb') as f:
                    audio_data = f.read()

                # Clean up
                Path(input_file).unlink(missing_ok=True)
                Path(output_file).unlink(missing_ok=True)

                # Play audio if available
                self._play_audio(audio_data)

                return audio_data
            else:
                # Non-blocking: return immediately
                Path(input_file).unlink(missing_ok=True)
                return None

        except subprocess.TimeoutExpired:
            logger.error("Piper synthesis timed out")
            return None
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return None

    def _get_model_flag(self) -> str:
        """Get model path or name for piper."""
        if self.model_path and Path(self.model_path).exists():
            return str(self.model_path)
        return self.voice

    def _play_audio(self, audio_data: bytes):
        """Play audio through speakers."""
        try:
            import pyaudio

            # Parse WAV header
            import wave

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(audio_data)
                wav_file = f.name

            wf = wave.open(wav_file, 'rb')

            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )

            logger.debug("Playing audio...")
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

        except ImportError:
            logger.warning("PyAudio not available for playback")
        except Exception as e:
            logger.error(f"Audio playback error: {e}")

    def synthesize_to_file(self, text: str, output_path: str):
        """
        Synthesize speech and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save WAV file
        """
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(text)
                input_file = f.name

            cmd = [
                "piper",
                "--model", self._get_model_flag(),
                "--output-file", output_path,
            ]

            if self._speaker_id:
                cmd.extend(["--speaker", str(self._speaker_id)])

            cmd.append(input_file)

            subprocess.run(cmd, timeout=30, check=True)

            Path(input_file).unlink(missing_ok=True)
            logger.info(f"Audio saved to {output_path}")

        except Exception as e:
            logger.error(f"Error synthesizing to file: {e}")

    def set_voice(self, voice: str):
        """Change TTS voice."""
        self.voice = voice

    def set_speaker(self, speaker_id: int):
        """Set speaker ID for multi-speaker models."""
        self._speaker_id = speaker_id

    def cleanup(self):
        """Cleanup resources."""
        logger.info("Piper TTS cleanup complete")

    @staticmethod
    def download_voice(voice_name: str, destination: str = "."):
        """
        Download a voice model.

        Args:
            voice_name: Name of voice to download (e.g., 'en_US-lessac-medium')
            destination: Directory to save voice files
        """
        cmd = ["piper-download", voice_name, destination]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info(f"Downloaded voice: {voice_name}")
            else:
                logger.error(f"Download failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error downloading voice: {e}")
