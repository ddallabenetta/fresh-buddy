"""Tests for the TTS service."""

import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

# Add service code to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "tts"))

from audio_utils import apply_volume


class TestTTSServiceVolume(unittest.TestCase):
    """Verify that the service attenuates generated WAV files."""

    def test_apply_volume_scales_pcm_samples(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name

        try:
            with wave.open(wav_path, "wb") as writer:
                writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                writer.writeframes(struct.pack("<hh", 1000, -1000))

            apply_volume(wav_path, 0.5)

            with wave.open(wav_path, "rb") as reader:
                frames = reader.readframes(2)
                samples = struct.unpack("<hh", frames)

            self.assertEqual(samples, (500, -500))
        finally:
            Path(wav_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
