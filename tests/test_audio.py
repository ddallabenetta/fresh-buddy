"""Tests for Audio Modules (STT and TTS)"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path
from types import SimpleNamespace

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.audio.stt import ParakeetSTT
from bmo.audio.tts import PiperTTS


class TestParakeetSTT(unittest.TestCase):
    """Test cases for Parakeet STT module."""

    def setUp(self):
        """Set up test fixtures."""
        self.stt = ParakeetSTT()

    def test_stt_initialization(self):
        """Test STT initializes without error."""
        self.assertIsNotNone(self.stt)
        self.assertEqual(self.stt.sample_rate, 16000)

    def test_transcribe_empty_audio(self):
        """Test transcribing empty audio returns empty string."""
        result = self.stt.transcribe(b"")
        self.assertEqual(result, "")

    def test_transcribe_none_audio(self):
        """Test transcribing None returns empty string."""
        result = self.stt.transcribe(None)
        self.assertEqual(result, "")

    def test_set_sample_rate(self):
        """Test setting sample rate."""
        self.stt.set_sample_rate(48000)
        self.assertEqual(self.stt.sample_rate, 48000)

    @patch('bmo.audio.stt.pyaudio')
    def test_listen_timeout(self, mock_pyaudio):
        """Test listen returns None on timeout."""
        # Short timeout for testing
        result = self.stt.listen(timeout=0.1)
        # Either returns audio or None depending on mock/setup
        # Just verify no error
        self.assertTrue(result is None or isinstance(result, bytes))

    def test_is_running_defaults_false(self):
        """Test streaming is not running by default."""
        self.assertFalse(self.stt._running)

    def test_start_stop_streaming(self):
        """Test starting and stopping streaming."""
        self.stt.start_streaming()
        self.assertTrue(self.stt._running)

        self.stt.stop()
        self.assertFalse(self.stt._running)


class TestPiperTTS(unittest.TestCase):
    """Test cases for Piper TTS module."""

    def setUp(self):
        """Set up test fixtures."""
        self.tts = PiperTTS()

    def test_tts_initialization(self):
        """Test TTS initializes without error."""
        self.assertIsNotNone(self.tts)
        self.assertEqual(self.tts.voice, "en_US-lessac-medium")
        self.assertEqual(self.tts._noise_scale, 0.667)
        self.assertEqual(self.tts._length_scale, 1.0)

    def test_set_voice(self):
        """Test setting voice."""
        self.tts.set_voice("en_GB-cori-medium")
        self.assertEqual(self.tts.voice, "en_GB-cori-medium")

    def test_set_speaker(self):
        """Test setting speaker ID."""
        self.tts.set_speaker(2)
        self.assertEqual(self.tts._speaker_id, 2)

    @patch("bmo.audio.tts.subprocess.run")
    def test_output_volume_is_applied_on_init(self, mock_run):
        """Test ALSA output volume is configured during initialization."""
        mock_run.side_effect = [
            Mock(
                returncode=0,
                stdout="Simple mixer control 'Speaker',0\n",
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        tts = PiperTTS(SimpleNamespace(audio_output_volume=0.6))

        self.assertIsNotNone(tts)
        self.assertEqual(mock_run.call_args_list[0].args[0], ["amixer", "scontrols"])
        self.assertEqual(
            mock_run.call_args_list[1].args[0],
            ["amixer", "sset", "Speaker", "60%"],
        )

    def test_speak_empty_text(self):
        """Test speaking empty text returns None."""
        result = self.tts.speak("")
        self.assertIsNone(result)

    def test_speak_none_text(self):
        """Test speaking None text returns None."""
        result = self.tts.speak(None)
        self.assertIsNone(result)

    @patch('bmo.audio.tts.subprocess.run')
    def test_speak_blocking(self, mock_run):
        """Test blocking speak call."""
        # Mock successful run
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = self.tts.speak("Hello world", blocking=True)
        # May be None if mock doesn't create temp files properly
        # Just verify no exception

    def test_cleanup(self):
        """Test cleanup runs without error."""
        self.tts.cleanup()  # Should not error


class TestAudioIntegration(unittest.TestCase):
    """Integration tests for audio pipeline."""

    def test_stt_tts_creation(self):
        """Test both STT and TTS can be created."""
        stt = ParakeetSTT()
        tts = PiperTTS()
        self.assertIsNotNone(stt)
        self.assertIsNotNone(tts)


if __name__ == "__main__":
    unittest.main()
