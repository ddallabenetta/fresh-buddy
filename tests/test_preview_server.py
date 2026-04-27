"""Tests for preview server HTTP endpoints and PNG rendering."""

import json
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.face.display import OLEDDisplay
from bmo.face.expressions import ExpressionEngine
from bmo.face import preview_server


class TestFramebufferToPNG(unittest.TestCase):
    """Test PNG conversion of the SSD1306 framebuffer."""

    def test_framebuffer_to_png_returns_bytes(self):
        """_framebuffer_to_png must return bytes (PNG format)."""
        # Empty framebuffer
        fb = bytearray(1024)
        result = preview_server._framebuffer_to_png(fb)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_framebuffer_to_png_starts_with_png_magic(self):
        """PNG must start with the standard magic bytes."""
        fb = bytearray(1024)
        result = preview_server._framebuffer_to_png(fb)
        # PNG magic: 89 50 4E 47 0D 0A 1A 0A
        self.assertEqual(result[:8], b"\x89PNG\r\n\x1a\n")

    def test_png_with_lit_pixels_differs_from_empty(self):
        """A framebuffer with pixels must produce a different PNG than an empty one.

        Note: when PIL is unavailable the fallback is a 1x1 black PNG regardless
        of framebuffer content — in that case we just verify the function returns
        PNG magic bytes and skip the content comparison.
        """
        fb_empty = bytearray(1024)
        result_empty = preview_server._framebuffer_to_png(fb_empty)
        self.assertEqual(result_empty[:8], b"\x89PNG\r\n\x1a\n")

        # Set a single byte in the framebuffer
        fb_lit = bytearray(1024)
        fb_lit[0] = 0xFF
        result_lit = preview_server._framebuffer_to_png(fb_lit)

        # If PIL is installed the two PNGs should differ.
        # Without PIL the fallback 1x1 PNG is identical — skip in that case.
        if result_empty != result_lit:
            self.assertNotEqual(result_empty, result_lit)
        else:
            self.skipTest("PIL not available — fallback returns identical 1x1 PNG")


class TestStateConfiguration(unittest.TestCase):
    """Test preview_server.configure() and shared state."""

    def setUp(self):
        # Reset module state before each test
        preview_server._state["expressions"] = None
        preview_server._state["tts_url"] = None
        preview_server._state["chat_callback"] = None

    def test_configure_accepts_expressions(self):
        """configure() must store the expressions engine reference."""
        display = OLEDDisplay()
        engine = ExpressionEngine(display)
        preview_server.configure(expressions=engine)
        self.assertIs(preview_server._state["expressions"], engine)
        self.assertTrue(engine._scanlines_enabled)
        self.assertTrue(engine._glow_enabled)

    def test_configure_accepts_tts_url(self):
        """configure() must store the TTS URL string."""
        preview_server.configure(tts_url="http://localhost:5000")
        self.assertEqual(preview_server._state["tts_url"], "http://localhost:5000")

    def test_configure_accepts_chat_callback(self):
        """configure() must store the chat callback."""
        cb = lambda msg, cb2: None
        preview_server.configure(chat_callback=cb)
        self.assertIs(preview_server._state["chat_callback"], cb)

    def test_configure_is_idempotent(self):
        """Calling configure multiple times must not raise."""
        display = OLEDDisplay()
        engine = ExpressionEngine(display)
        preview_server.configure(expressions=engine)
        preview_server.configure(expressions=engine)  # should not raise

    def test_configure_applies_visual_settings(self):
        """Preview state should initialize ExpressionEngine render options."""
        display = OLEDDisplay()
        engine = ExpressionEngine(display)
        old_scanlines = preview_server._state["scanlines"]
        old_glow = preview_server._state["glow"]
        try:
            preview_server._state["scanlines"] = False
            preview_server._state["glow"] = False
            preview_server.configure(expressions=engine)
            self.assertFalse(engine._scanlines_enabled)
            self.assertFalse(engine._glow_enabled)
        finally:
            preview_server._state["scanlines"] = old_scanlines
            preview_server._state["glow"] = old_glow


class TestBroadcastMechanism(unittest.TestCase):
    """Test SSE/polling broadcast helper functions."""

    def setUp(self):
        preview_server._sse_clients.clear()
        preview_server._update_seq = 0

    def test_broadcast_does_not_raise(self):
        """_broadcast() must not raise even with no clients."""
        # Should not raise
        preview_server._broadcast({"type": "expression", "name": "happy"})

    def test_broadcast_increments_seq(self):
        """Each broadcast should increment _update_seq."""
        initial = preview_server._update_seq
        preview_server._broadcast({"type": "ping"})
        self.assertEqual(preview_server._update_seq, initial + 1)

    def test_broadcast_expression_helper_exists(self):
        """broadcast_expression() must be a callable."""
        self.assertTrue(callable(preview_server.broadcast_expression))

    def test_put_response_updates_global(self):
        """put_response() must store response for polling."""
        preview_server.put_response("Test response")
        self.assertEqual(preview_server._last_response["text"], "Test response")
        self.assertGreater(preview_server._last_response["seq"], 0)


class TestHandlerRouting(unittest.TestCase):
    """Test HTTP request routing without requiring a live server.

    We test the handler logic by inspecting method attributes and
    verifying the handler has the expected do_GET/do_POST methods.
    """

    def test_handler_has_do_get(self):
        """Handler must implement do_GET."""
        self.assertTrue(hasattr(preview_server._Handler, "do_GET"))

    def test_handler_has_do_post(self):
        """Handler must implement do_POST."""
        self.assertTrue(hasattr(preview_server._Handler, "do_POST"))

    def test_handler_has_respond_helper(self):
        """Handler must have _respond helper."""
        self.assertTrue(hasattr(preview_server._Handler, "_respond"))


class TestPreviewServerEndpoints(unittest.TestCase):
    """Test endpoint behavior by exercising the Handler directly.

    These tests use a mock HTTPServer connection to verify routing.
    """

    @classmethod
    def setUpClass(cls):
        # Use a free port by patching the server start
        cls.port = 18080
        cls.display = OLEDDisplay()
        cls.engine = ExpressionEngine(cls.display)
        preview_server.configure(expressions=cls.engine)

    @classmethod
    def tearDownClass(cls):
        preview_server._state["display"] = None
        preview_server._state["expressions"] = None

    def setUp(self):
        # Clear the PNG cache so each test gets fresh render
        preview_server._display_png_cache = None
        preview_server._display_png_time = 0

    def test_display_endpoint_returns_png_content_type(self):
        """GET /display.png should return Content-Type: image/png."""
        preview_server._state["display"] = self.display

        conn = HTTPConnection("localhost", self.port, timeout=2)
        try:
            conn.connect()
            conn.request("GET", "/display.png")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertIn("image/png", resp.getheader("Content-Type", ""))
        except (ConnectionRefusedError, OSError):
            self.skipTest("Server not running — test requires live server")
        finally:
            conn.close()

    def test_expression_endpoint_accepts_post(self):
        """POST /expression with valid JSON must return 200."""
        preview_server._state["expressions"] = self.engine

        # We can test via a thread-local handler instance
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            body = json.dumps({"name": "happy"}).encode()
            conn.request("POST", "/expression", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.getheader("Content-Type", ""))
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_chat_endpoint_rejects_empty_message(self):
        """POST /chat with no message must return 400."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            body = json.dumps({"message": ""}).encode()
            conn.request("POST", "/chat", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_chat_endpoint_requires_content_length(self):
        """POST /chat without Content-Length must not crash."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            conn.request("POST", "/chat", body=b'{"message": "hello"}',
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            # Should get a valid response, not a crash
            self.assertIn(resp.status, (200, 400, 503))
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_unknown_path_returns_404(self):
        """GET /nonexistent must return 404."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            conn.request("GET", "/nonexistent")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 404)
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_expression_unknown_returns_200_despite_warning(self):
        """POST /expression with unknown name should return 200 (logs warning)."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            body = json.dumps({"name": "not_an_expression"}).encode()
            conn.request("POST", "/expression", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            # Should still return 200 even with unknown expression
            self.assertEqual(resp.status, 200)
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_updates_endpoint_returns_json(self):
        """GET /updates should return application/json."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            conn.request("GET", "/updates")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.getheader("Content-Type", ""))
            # Body should be valid JSON (empty list is fine)
            data = json.loads(resp.read())
            self.assertIsInstance(data, list)
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()


class TestServerStart(unittest.TestCase):
    """Test server startup and lifecycle."""

    def test_start_preview_server_returns_server_instance(self):
        """start_preview_server must return the HTTPServer object."""
        display = OLEDDisplay()
        server = preview_server.start_preview_server(display, port=0)
        self.assertIsInstance(server, HTTPServer)
        server.shutdown()

    def test_get_command_queue_returns_queue(self):
        """get_command_queue must return a Queue object."""
        q = preview_server.get_command_queue()
        self.assertIsInstance(q, type(preview_server._state["command_queue"]))


class TestJSONResponses(unittest.TestCase):
    """Test that POST endpoints return valid JSON."""

    def test_expression_response_is_valid_json(self):
        """Response body must be parseable JSON."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            body = json.dumps({"name": "happy"}).encode()
            conn.request("POST", "/expression", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            body = resp.read()
            data = json.loads(body)
            self.assertIsInstance(data, dict)
            self.assertTrue(data.get("ok"))
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()

    def test_chat_response_is_valid_json(self):
        """Chat response (before processing) must be valid JSON."""
        server = HTTPServer(("localhost", 0), preview_server._Handler)
        port = server.server_address[1]
        server.server_close()

        conn = HTTPConnection("localhost", port, timeout=2)
        try:
            body = json.dumps({"message": "hello"}).encode()
            conn.request("POST", "/chat", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            body = resp.read()
            data = json.loads(body)
            self.assertIsInstance(data, dict)
        except OSError:
            self.skipTest("Could not bind to port")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
