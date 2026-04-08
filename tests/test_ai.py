"""Tests for AI Modules (Nemotron and Meeting Assistant)"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.ai.nemotron import NemotronLLM
from bmo.ai.meeting import MeetingAssistant


class TestNemotronLLM(unittest.TestCase):
    """Test cases for Nemotron LLM module."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = NemotronLLM()

    def test_llm_initialization(self):
        """Test LLM initializes without error."""
        self.assertIsNotNone(self.llm)
        self.assertEqual(self.llm.temperature, 0.7)
        self.assertEqual(self.llm.max_tokens, 512)

    def test_mock_mode_when_not_initialized(self):
        """Test that mock responses are returned when not initialized."""
        # Should be in mock mode without actual model
        self.assertFalse(self.llm._initialized)

    def test_generate_mock_response(self):
        """Test generate returns mock response in mock mode."""
        response = self.llm.generate("Hello")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)

    def test_generate_with_system_prompt(self):
        """Test generate respects system prompt."""
        response = self.llm.generate("Hello", system_prompt="You are BMO.")
        self.assertIsInstance(response, str)

    def test_chat_mock(self):
        """Test chat returns mock response."""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        response = self.llm.chat(messages)
        self.assertIsInstance(response, str)

    def test_summarize(self):
        """Test summarize method exists and works."""
        long_text = "This is a test. " * 50
        summary = self.llm.summarize(long_text, max_length=20)
        self.assertIsInstance(summary, str)

    def test_set_temperature(self):
        """Test setting temperature."""
        self.llm.set_temperature(1.0)
        self.assertEqual(self.llm.temperature, 1.0)

        # Test bounds
        self.llm.set_temperature(5.0)  # Should cap at 2.0
        self.assertEqual(self.llm.temperature, 2.0)

        self.llm.set_temperature(-1.0)  # Should floor at 0.0
        self.assertEqual(self.llm.temperature, 0.0)

    def test_set_max_tokens(self):
        """Test setting max tokens."""
        self.llm.set_max_tokens(1024)
        self.assertEqual(self.llm.max_tokens, 1024)

    def test_is_initialized(self):
        """Test is_initialized returns correct state."""
        # Without real model, should return False
        self.assertFalse(self.llm.is_initialized())


class TestMeetingAssistant(unittest.TestCase):
    """Test cases for Meeting Assistant."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_llm = Mock()
        self.mock_stt = Mock()
        self.mock_tts = Mock()

        self.meeting = MeetingAssistant(
            llm=self.mock_llm,
            stt=self.mock_stt,
            tts=self.mock_tts
        )

    def test_meeting_initialization(self):
        """Test meeting assistant initializes."""
        self.assertIsNotNone(self.meeting)
        self.assertFalse(self.meeting.is_recording)
        self.assertEqual(len(self.meeting.transcript), 0)

    def test_start_recording(self):
        """Test starting a recording."""
        self.meeting.start_recording()
        self.assertTrue(self.meeting.is_recording)
        self.assertIsNotNone(self.meeting.meeting_start_time)
        self.assertIsNotNone(self.meeting.meeting_id)

    def test_stop_recording(self):
        """Test stopping a recording."""
        self.meeting.start_recording()
        self.meeting.stop_recording()
        self.assertFalse(self.meeting.is_recording)

    def test_process_speech_not_recording(self):
        """Test processing speech when not recording does nothing."""
        self.meeting.process_speech("Hello")
        self.assertEqual(len(self.meeting.transcript), 0)

    def test_process_speech_while_recording(self):
        """Test processing speech during recording."""
        self.meeting.start_recording()
        self.meeting.process_speech("Hello world", speaker="Alice")
        self.assertEqual(len(self.meeting.transcript), 1)
        self.assertEqual(self.meeting.transcript[0]["text"], "Hello world")
        self.assertEqual(self.meeting.transcript[0]["speaker"], "Alice")

    def test_get_transcript_empty(self):
        """Test getting transcript when empty."""
        result = self.meeting.get_transcript()
        self.assertEqual(result, "No transcript available.")

    def test_get_summary_empty(self):
        """Test getting summary when no content."""
        result = self.meeting.get_summary()
        self.assertEqual(result, "No meeting content to summarize.")

    def test_get_minutes_structure(self):
        """Test meeting minutes has correct structure."""
        minutes = self.meeting.get_minutes()
        self.assertIn("meeting_id", minutes)
        self.assertIn("summary", minutes)
        self.assertIn("action_items", minutes)
        self.assertIn("decisions", minutes)
        self.assertIn("participants", minutes)

    def test_list_meetings(self):
        """Test listing meetings returns list."""
        meetings = self.meeting.list_meetings()
        self.assertIsInstance(meetings, list)


class TestAIIntegration(unittest.TestCase):
    """Integration tests for AI pipeline."""

    def test_nemotron_and_meeting_creation(self):
        """Test both modules can be created together."""
        llm = NemotronLLM()
        stt = ParakeetSTT()
        tts = PiperTTS()
        meeting = MeetingAssistant(llm, stt, tts)

        self.assertIsNotNone(llm)
        self.assertIsNotNone(meeting)

    def test_meeting_with_mock_llm(self):
        """Test meeting uses mock LLM for mock responses."""
        mock_llm = Mock()
        mock_llm.summarize.return_value = "Test summary"
        mock_llm.extract_action_items.return_value = []

        meeting = MeetingAssistant(
            llm=mock_llm,
            stt=Mock(),
            tts=Mock()
        )

        meeting.start_recording()
        meeting.process_speech("Test speech")
        summary = meeting.get_summary()

        self.assertEqual(summary, "Test summary")
        mock_llm.summarize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
