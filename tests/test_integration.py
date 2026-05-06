"""End-to-end integration tests for Fresh Buddy — all components together."""

import queue
import threading
import time
import unittest
from unittest.mock import patch, MagicMock, Mock, call
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.face.display import OLEDDisplay
from bmo.face.expressions import ExpressionEngine, Expression
from bmo.face import preview_server
from bmo.main import FreshBuddy
from bmo.config import Config


# ── FreshBuddy startup with all components ──────────────────────────────────

class TestFreshBuddyStartup(unittest.TestCase):
    """Test that FreshBuddy initializes all components without error."""

    def setUp(self):
        # Mock all hardware / network dependencies so we can instantiate FreshBuddy
        self.config_patcher = patch("bmo.main.Config")
        self.display_patcher = patch("bmo.main.OLEDDisplay")
        self.stt_patcher = patch("bmo.main.ParakeetSTT")
        self.tts_patcher = patch("bmo.main.PiperTTS")
        self.llm_patcher = patch("bmo.main.LLMClient")
        self.meeting_patcher = patch("bmo.main.MeetingAssistant")
        self.ps_configure_patcher = patch("bmo.face.preview_server.configure")

        self.mock_config_cls = self.config_patcher.start()
        self.mock_config = MagicMock()
        self.mock_config_cls.load.return_value = self.mock_config
        self.mock_config.tts_endpoint = "http://localhost:5000"
        self.mock_config.first_message = "Messaggio iniziale personalizzato."

        self.mock_display = self.display_patcher.start()
        self.mock_stt = self.stt_patcher.start()
        self.mock_tts = self.tts_patcher.start()
        self.mock_llm = self.llm_patcher.start()
        self.mock_meeting = self.meeting_patcher.start()
        self.ps_configure_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.display_patcher.stop()
        self.stt_patcher.stop()
        self.tts_patcher.stop()
        self.llm_patcher.stop()
        self.meeting_patcher.stop()
        self.ps_configure_patcher.stop()

    def test_freshbuddy_instantiates_without_error(self):
        """FreshBuddy.__init__ must not raise."""
        buddy = FreshBuddy(self.mock_config)
        self.assertIsNotNone(buddy)

    def test_freshbuddy_sets_running_false_initially(self):
        """FreshBuddy.running must be False after __init__."""
        buddy = FreshBuddy(self.mock_config)
        self.assertFalse(buddy.running)

    def test_freshbuddy_has_display_attribute(self):
        """FreshBuddy must hold a reference to the display."""
        buddy = FreshBuddy(self.mock_config)
        self.assertTrue(hasattr(buddy, "display"))

    def test_freshbuddy_has_expressions_attribute(self):
        """FreshBuddy must hold a reference to the expression engine."""
        buddy = FreshBuddy(self.mock_config)
        self.assertTrue(hasattr(buddy, "expressions"))

    def test_preview_server_configure_called(self):
        """FreshBuddy must call preview_server.configure() at init."""
        FreshBuddy(self.mock_config)
        preview_server.configure.assert_called_once()

    def test_startup_calls_show_expression_happy(self):
        """startup() must show the happy expression."""
        buddy = FreshBuddy(self.mock_config)
        with patch.object(buddy.expressions, "show_expression") as mock_show:
            buddy.startup()
            mock_show.assert_any_call("happy")

    def test_startup_calls_speak(self):
        """startup() must speak a greeting."""
        buddy = FreshBuddy(self.mock_config)
        with patch.object(buddy, "_speak") as mock_speak:
            buddy.startup()
            mock_speak.assert_called_once()
            args, _ = mock_speak.call_args
            self.assertEqual(args[0], "Messaggio iniziale personalizzato.")


# ── Expression sequence: startup -> listening -> speaking -> happy -> neutral ─

class TestExpressionSequence(unittest.TestCase):
    """Test realistic expression sequences through the full pipeline."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)
        preview_server.configure(expressions=self.engine)

    def tearDown(self):
        preview_server._state["expressions"] = None

    @patch("time.sleep")
    def test_sequence_startup_to_happy(self, mock_sleep):
        """Test a realistic startup → happy sequence."""
        mock_sleep.side_effect = Exception("stop")

        # Simulate startup
        self.engine.show_expression("happy")
        self.assertEqual(self.engine.current, Expression.HAPPY)

        # Switch to neutral (after conversation ends)
        self.engine.show_expression("neutral")
        self.assertEqual(self.engine.current, Expression.NEUTRAL)

    @patch("time.sleep")
    def test_sequence_startup_to_listening(self, mock_sleep):
        """Test startup → listening sequence."""
        mock_sleep.side_effect = Exception("stop")

        self.engine.show_expression("happy")
        self.engine.show_expression("listening")
        self.assertEqual(self.engine.current, Expression.LISTENING)

    @patch("time.sleep")
    def test_sequence_startup_to_speaking(self, mock_sleep):
        """Test startup → speaking sequence."""
        mock_sleep.side_effect = Exception("stop")

        self.engine.show_expression("happy")
        self.engine.show_expression("speaking")
        self.assertEqual(self.engine.current, Expression.SPEAKING)

    @patch("time.sleep")
    def test_full_conversation_sequence(self, mock_sleep):
        """Simulate: happy → listening → thinking → speaking → happy → neutral."""
        mock_sleep.side_effect = Exception("stop")

        sequence = [
            ("happy", Expression.HAPPY),
            ("listening", Expression.LISTENING),
            ("thinking", Expression.THINKING),
            ("speaking", Expression.SPEAKING),
            ("happy", Expression.HAPPY),
            ("neutral", Expression.NEUTRAL),
        ]

        for name, expr in sequence:
            self.engine.show_expression(name)
            self.assertEqual(
                self.engine.current, expr,
                f"Expected {expr.value} after '{name}'",
            )


# ── Meeting mode expression changes ──────────────────────────────────────────

class TestMeetingModeExpressions(unittest.TestCase):
    """Test that meeting assistant correctly drives expression changes."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    @patch("time.sleep")
    def test_meeting_mode_uses_recording_expression(self, mock_sleep):
        """Meeting recording should use the recording expression."""
        mock_sleep.side_effect = Exception("stop")
        self.engine.show_expression("recording")
        self.assertEqual(self.engine.current, Expression.RECORDING)

    @patch("time.sleep")
    def test_meeting_stop_returns_to_neutral(self, mock_sleep):
        """After meeting ends, expression should return to neutral."""
        mock_sleep.side_effect = Exception("stop")

        self.engine.show_expression("recording")
        self.engine.show_expression("neutral")
        self.assertEqual(self.engine.current, Expression.NEUTRAL)

    @patch("time.sleep")
    def test_excited_expression_available_for_meeting_highlights(self, mock_sleep):
        """EXCITED expression should be available for meeting highlights."""
        mock_sleep.side_effect = Exception("stop")
        self.engine.show_expression("excited")
        self.assertEqual(self.engine.current, Expression.EXCITED)


# ── Preview server integration with expression engine ───────────────────────

class TestPreviewServerIntegration(unittest.TestCase):
    """Test preview server endpoints with a real ExpressionEngine."""

    @classmethod
    def setUpClass(cls):
        cls.display = OLEDDisplay()
        cls.engine = ExpressionEngine(cls.display)
        preview_server.configure(expressions=cls.engine)
        # Start a real server on port 0 (OS picks free port)
        cls.server = preview_server.start_preview_server(cls.display, port=0)
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        preview_server._state["display"] = None
        preview_server._state["expressions"] = None

    def test_display_png_endpoint(self):
        """GET /display.png must return PNG bytes."""
        from http.client import HTTPConnection
        conn = HTTPConnection("localhost", self.port, timeout=5)
        conn.request("GET", "/display.png")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn("image/png", resp.getheader("Content-Type", ""))
        body = resp.read()
        self.assertGreater(len(body), 0)
        self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")
        conn.close()

    def test_expression_endpoint_sets_expression(self):
        """POST /expression must change the active expression."""
        from http.client import HTTPConnection
        import json

        conn = HTTPConnection("localhost", self.port, timeout=5)
        body = json.dumps({"name": "happy"}).encode()
        conn.request("POST", "/expression", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()

        # Give the thread time to run show_expression
        time.sleep(0.1)
        self.assertEqual(self.engine.current, Expression.HAPPY)

    def test_chat_endpoint_returns_ok(self):
        """POST /chat with a message must return 200 + JSON with ok:true."""
        from http.client import HTTPConnection
        import json

        conn = HTTPConnection("localhost", self.port, timeout=5)
        body = json.dumps({"message": "Hello Fresh Buddy"}).encode()
        conn.request("POST", "/chat", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read())
        self.assertTrue(data.get("ok"))
        conn.close()

    def test_updates_endpoint_returns_json_list(self):
        """GET /updates must return a JSON list."""
        import json
        from http.client import HTTPConnection

        conn = HTTPConnection("localhost", self.port, timeout=5)
        conn.request("GET", "/updates")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read())
        self.assertIsInstance(data, list)
        conn.close()

    def test_homepage_returns_html(self):
        """GET / must return HTML content."""
        from http.client import HTTPConnection

        conn = HTTPConnection("localhost", self.port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type", ""))
        body = resp.read()
        self.assertIn(b"Fresh Buddy", body)
        conn.close()


# ── Headless single-query mode ───────────────────────────────────────────────

class TestHeadlessMode(unittest.TestCase):
    """Test FreshBuddy.run_headless() — no voice, just LLM."""

    def setUp(self):
        self.config_patcher = patch("bmo.main.Config")
        self.display_patcher = patch("bmo.main.OLEDDisplay")
        self.stt_patcher = patch("bmo.main.ParakeetSTT")
        self.tts_patcher = patch("bmo.main.PiperTTS")
        self.llm_patcher = patch("bmo.main.LLMClient")
        self.meeting_patcher = patch("bmo.main.MeetingAssistant")
        self.ps_configure_patcher = patch("bmo.face.preview_server.configure")

        self.mock_config_cls = self.config_patcher.start()
        self.mock_config = MagicMock()
        self.mock_config_cls.load.return_value = self.mock_config
        self.mock_display = self.display_patcher.start()
        self.mock_stt = self.stt_patcher.start()
        self.mock_tts = self.tts_patcher.start()
        self.mock_llm = self.llm_patcher.start()
        self.mock_meeting = self.meeting_patcher.start()
        self.ps_configure_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.display_patcher.stop()
        self.stt_patcher.stop()
        self.tts_patcher.stop()
        self.llm_patcher.stop()
        self.meeting_patcher.stop()
        self.ps_configure_patcher.stop()

    def test_run_headless_returns_llm_response(self):
        """run_headless must return the LLM-generated response."""
        buddy = FreshBuddy(self.mock_config)
        buddy.llm.generate.return_value = "Hello! How can I help you?"

        result = buddy.run_headless("Hi")
        self.assertEqual(result, "Hello! How can I help you?")
        buddy.llm.generate.assert_called_once_with("Hi")

    def test_run_headless_does_not_use_voice(self):
        """run_headless must not call TTS or STT."""
        buddy = FreshBuddy(self.mock_config)
        buddy.llm.generate.return_value = "Response"

        buddy.run_headless("Hello")
        buddy.tts.speak.assert_not_called()
        buddy.stt.listen.assert_not_called()


# ── Signal handling and shutdown ────────────────────────────────────────────

class TestShutdownSequence(unittest.TestCase):
    """Test clean shutdown of FreshBuddy."""

    def setUp(self):
        self.config_patcher = patch("bmo.main.Config")
        self.display_patcher = patch("bmo.main.OLEDDisplay")
        self.stt_patcher = patch("bmo.main.ParakeetSTT")
        self.tts_patcher = patch("bmo.main.PiperTTS")
        self.llm_patcher = patch("bmo.main.LLMClient")
        self.meeting_patcher = patch("bmo.main.MeetingAssistant")
        self.ps_configure_patcher = patch("bmo.face.preview_server.configure")

        self.mock_config_cls = self.config_patcher.start()
        self.mock_config = MagicMock()
        self.mock_config_cls.load.return_value = self.mock_config
        self.mock_display = self.display_patcher.start()
        self.mock_stt = self.stt_patcher.start()
        self.mock_tts = self.tts_patcher.start()
        self.mock_llm = self.llm_patcher.start()
        self.mock_meeting = self.meeting_patcher.start()
        self.ps_configure_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.display_patcher.stop()
        self.stt_patcher.stop()
        self.tts_patcher.stop()
        self.llm_patcher.stop()
        self.meeting_patcher.stop()
        self.ps_configure_patcher.stop()

    def test_shutdown_calls_sleeping_expression(self):
        """shutdown() must set expression to sleeping."""
        buddy = FreshBuddy(self.mock_config)
        with patch.object(buddy.expressions, "show_expression") as mock_show:
            buddy.shutdown()
            mock_show.assert_called_with("sleeping")

    def test_shutdown_stops_stt(self):
        """shutdown() must call stt.stop() if available."""
        buddy = FreshBuddy(self.mock_config)
        buddy.shutdown()
        buddy.stt.stop.assert_called()

    def test_shutdown_calls_tts_cleanup(self):
        """shutdown() must call tts.cleanup() if available."""
        buddy = FreshBuddy(self.mock_config)
        buddy.shutdown()
        buddy.tts.cleanup.assert_called()


if __name__ == "__main__":
    unittest.main()
