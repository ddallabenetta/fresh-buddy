"""OLED Display Preview Server — development only.

Interactive dashboard:
  GET  /             → HTML dev console (full chat)
  GET  /display.png  → current framebuffer as PNG (auto-refreshed)
  GET  /events       → SSE stream for real-time expression updates
  POST /expression   → {"name": "happy"} — trigger an expression
  POST /speak        → {"text": "..."} — proxy to TTS, returns audio/wav
  POST /chat         → {"message": "..."} — send chat message, returns response
"""

import io
import json
import logging
import queue
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

_SCALE = 4  # upscale 128×64 → 512×256 for readability

# Shared state — populated by configure() after all components are ready
_state: dict = {
    "display": None,
    "expressions": None,
    "tts_url": None,
    "command_queue": queue.Queue(),
    "chat_callback": None,  # async callback for chat messages (message, callback(response))
}

# Last response from a simulated command — polled by the browser
_last_response: dict = {"text": None, "seq": 0}

# SSE clients for real-time updates
_sse_clients: list = []
_sse_lock = threading.Lock()

# Polling-based updates (simpler than SSE)
_update_queue: queue.Queue = queue.Queue()
_update_seq: int = 0

# Display PNG cache
_display_png_cache: bytes = None
_display_png_time: float = 0
_display_png_ttl: float = 0.5  # seconds

_EXPRESSIONS = [
    "neutral",
    "happy",
    "sad",
    "excited",
    "confused",
    "thinking",
    "listening",
    "speaking",
    "recording",
    "sleeping",
]


def _build_html() -> str:
    """Build the dev console HTML with full chat interface."""
    expr_buttons = "\n      ".join(
        f'<button class="expr-btn" id="expr-{e}" onclick="sendExpression(\'{e}\')">{e}</button>'
        for e in _EXPRESSIONS
    )
    w = 128 * _SCALE
    h = 64 * _SCALE

    return (
        "<!doctype html>\n"
        '<html lang="it">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Fresh Buddy \u2014 Dev Console</title>\n"
        "  <style>\n"
        "    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\n"
        "    body {\n"
        "      background: #0a0a0a; color: #ddd;\n"
        "      font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;\n"
        "      display: flex; flex-direction: column; align-items: center;\n"
        "      padding: 16px; gap: 16px;\n"
        "      min-height: 100vh;\n"
        "    }\n"
        "    h1 { color: #fff; font-size: 1rem; letter-spacing: 2px; text-transform: uppercase; }\n"
        "    h2 { font-size: .7rem; color: #888; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }\n"
        "    .top-bar { display: flex; gap: 16px; width: 100%; max-width: 900px; align-items: flex-start; }\n"
        "    #oled-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; flex-shrink: 0; }\n"
        "    #fb { image-rendering: pixelated; border: 2px solid #333; border-radius: 4px; }\n"
        "    #oled-wrap p { color: #444; font-size: 10px; }\n"
        "    .card {\n"
        "      background: #141414; border: 1px solid #2a2a2a; border-radius: 8px;\n"
        "      padding: 12px; flex: 1;\n"
        "    }\n"
        "    #chat-container { display: flex; flex-direction: column; height: 320px; }\n"
        "    #chat-history {\n"
        "      flex: 1; overflow-y: auto; border: 1px solid #2a2a2a; border-radius: 4px;\n"
        "      padding: 10px; background: #0d0d0d; display: flex; flex-direction: column; gap: 8px;\n"
        "    }\n"
        "    .msg { max-width: 85%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.4; }\n"
        "    .msg.user { align-self: flex-end; background: #1565c0; color: #fff; border-bottom-right-radius: 2px; }\n"
        "    .msg.buddy { align-self: flex-start; background: #1a1a1a; border: 1px solid #333; color: #ccc; border-bottom-left-radius: 2px; }\n"
        "    .msg.buddy.thinking { border-color: #f59e0b; }\n"
        "    .msg.buddy.speaking { border-color: #22c55e; }\n"
        "    .msg.buddy .expr-tag { font-size: 10px; color: #888; margin-top: 4px; display: block; }\n"
        "    #chat-input-row { display: flex; gap: 8px; margin-top: 10px; }\n"
        "    #chat-input { flex: 1; background: #1a1a1a; border: 1px solid #333; color: #eee; border-radius: 20px; padding: 10px 16px; font-family: inherit; font-size: 13px; }\n"
        "    #chat-input:focus { outline: none; border-color: #555; }\n"
        "    #chat-input:disabled { opacity: 0.5; }\n"
        "    .send-btn { background: #22c55e; border: none; color: #fff; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; }\n"
        "    .send-btn:hover { background: #16a34a; }\n"
        "    .send-btn:disabled { background: #333; cursor: not-allowed; }\n"
        "    .expr-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; }\n"
        "    .expr-btn {\n"
        "      background: #1a1a1a; border: 1px solid #333; color: #888;\n"
        "      border-radius: 4px; padding: 5px 3px; font-size: 10px;\n"
        "      cursor: pointer; text-align: center; transition: all .15s;\n"
        "    }\n"
        "    .expr-btn:hover { background: #2e7d32; color: #fff; border-color: #388e3c; }\n"
        "    .expr-btn.active { background: #1b5e20; color: #a5d6a7; border-color: #2e7d32; }\n"
        "    .row { display: flex; gap: 8px; margin-top: 8px; }\n"
        "    input[type=text] {\n"
        "      flex: 1; background: #1a1a1a; border: 1px solid #333; color: #eee;\n"
        "      border-radius: 4px; padding: 8px 10px; font-family: inherit; font-size: 12px;\n"
        "    }\n"
        "    input[type=text]:focus { outline: none; border-color: #555; }\n"
        "    .btn {\n"
        "      background: #1565c0; border: none; color: #fff;\n"
        "      border-radius: 4px; padding: 8px 14px; font-family: inherit;\n"
        "      font-size: 11px; cursor: pointer; white-space: nowrap; transition: background .15s;\n"
        "    }\n"
        "    .btn:hover { background: #1976d2; }\n"
        "    .btn.green { background: #2e7d32; }\n"
        "    .btn.green:hover { background: #388e3c; }\n"
        "    #status { font-size: 10px; color: #555; min-height: 14px; margin-top: 6px; transition: color .3s; }\n"
        "    #status.ok  { color: #66bb6a; }\n"
        "    #status.err { color: #ef5350; }\n"
        "    .card-mini { background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; padding: 10px; }\n"
        "    .mini-row { display: flex; gap: 8px; align-items: center; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Fresh Buddy \u2014 Dev Console</h1>\n"
        '\n  <div class="top-bar">\n'
        '\n  <div id="oled-wrap" class="card">\n'
        "    <h2>Display</h2>\n"
        f'    <img id="fb" src="/display.png" width="{w}" height="{h}" alt="framebuffer">\n'
        "    <p>refresh: 100ms</p>\n"
        '    <div class="expr-grid" style="margin-top:10px;">\n'
        f"      {expr_buttons}\n"
        "    </div>\n"
        "  </div>\n"
        '\n  <div id="chat-container" class="card">\n'
        "    <h2>Chat</h2>\n"
        '    <div id="chat-history"></div>\n'
        '    <div id="chat-input-row">\n'
        '      <input id="chat-input" type="text" placeholder="Scrivi un messaggio..." autocomplete="off">\n'
        '      <button class="send-btn" id="send-btn" onclick="sendChat()">\u27a4</button>\n'
        "    </div>\n"
        "  </div>\n"
        "\n  </div>\n"
        '\n  <div class="card-mini" style="width:100%;max-width:900px;">\n'
        '    <div class="mini-row">\n'
        '      <input id="tts-text" type="text" placeholder="Test TTS..." value="Ciao!">\n'
        '      <button class="btn green" onclick="sendSpeak()">Parla</button>\n'
        "    </div>\n"
        '    <div id="status"></div>\n'
        "  </div>\n"
        "\n  <script>\n"
        "    // --- display refresh (1s interval, expressions via SSE) ---\n"
        "    setInterval(() => {\n"
        "      const img = document.getElementById('fb');\n"
        "      img.src = '/display.png?' + Date.now();\n"
        "    }, 1000);\n"
        "\n"
        "    // --- polling for updates (drains full queue each tick) ---\n"
        "    function processUpdate(data) {\n"
        "      if (!data || !data.type) return;\n"
        "      if (data.type === 'expression') {\n"
        "        document.querySelectorAll('.expr-btn').forEach(b => b.classList.remove('active'));\n"
        "        const btn = document.getElementById('expr-' + data.name);\n"
        "        if (btn) btn.classList.add('active');\n"
        "      } else if (data.type === 'chat_response') {\n"
        "        appendMessage('buddy', data.text, data.expression);\n"
        "        setChatInputEnabled(true);\n"
        "        autoPlayTTS(data.text);\n"
        "      } else if (data.type === 'thinking') {\n"
        "        appendMessage('buddy', data.text, 'thinking');\n"
        "      }\n"
        "    }\n"
        "    async function pollUpdates() {\n"
        "      try {\n"
        "        const r = await fetch('/updates');\n"
        "        if (r.ok) {\n"
        "          const updates = await r.json();\n"
        "          for (const data of updates) processUpdate(data);\n"
        "        }\n"
        "      } catch(err) {}\n"
        "    }\n"
        "    setInterval(pollUpdates, 800);\n"
        "\n"
        "    // --- helpers ---\n"
        "    function setStatus(id, msg, cls) {\n"
        "      const el = document.getElementById(id);\n"
        "      if (!el) return;\n"
        "      el.textContent = msg;\n"
        "      el.className = cls || '';\n"
        "    }\n"
        "\n"
        "    function setChatInputEnabled(enabled) {\n"
        "      const inp = document.getElementById('chat-input');\n"
        "      const btn = document.getElementById('send-btn');\n"
        "      if (inp) inp.disabled = !enabled;\n"
        "      if (btn) btn.disabled = !enabled;\n"
        "    }\n"
        "\n"
        "    function appendMessage(role, text, expr) {\n"
        "      const history = document.getElementById('chat-history');\n"
        "      if (!history || !text) return;\n"
        "      const div = document.createElement('div');\n"
        "      div.className = 'msg ' + role;\n"
        "      if (expr) div.className += ' ' + expr;\n"
        "      div.textContent = text;\n"
        "      if (role === 'buddy' && expr) {\n"
        "        const tag = document.createElement('span');\n"
        "        tag.className = 'expr-tag';\n"
        "        tag.textContent = expr;\n"
        "        div.appendChild(tag);\n"
        "      }\n"
        "      history.appendChild(div);\n"
        "      history.scrollTop = history.scrollHeight;\n"
        "    }\n"
        "\n"
        "    async function post(url, body) {\n"
        "      return fetch(url, {\n"
        "        method: 'POST',\n"
        "        headers: { 'Content-Type': 'application/json' },\n"
        "        body: JSON.stringify(body),\n"
        "      });\n"
        "    }\n"
        "\n"
        "    async function autoPlayTTS(text) {\n"
        "      if (!text) return;\n"
        "      try {\n"
        "        const r = await post('/speak', { text });\n"
        "        if (r.ok) {\n"
        "          const blob = await r.blob();\n"
        "          const url = URL.createObjectURL(blob);\n"
        "          const audio = new Audio(url);\n"
        "          audio.play();\n"
        "          audio.onended = () => URL.revokeObjectURL(url);\n"
        "        }\n"
        "      } catch(e) {}\n"
        "    }\n"
        "\n"
        "    // --- expressions ---\n"
        "    async function sendExpression(name) {\n"
        "      document.querySelectorAll('.expr-btn').forEach(b => b.classList.remove('active'));\n"
        "      document.getElementById('expr-' + name).classList.add('active');\n"
        "      await post('/expression', { name });\n"
        "    }\n"
        "\n"
        "    // --- chat ---\n"
        "    async function sendChat() {\n"
        "      const inp = document.getElementById('chat-input');\n"
        "      const text = inp.value.trim();\n"
        "      if (!text) return;\n"
        "      appendMessage('user', text);\n"
        "      inp.value = '';\n"
        "      setChatInputEnabled(false);\n"
        "      try {\n"
        "        const r = await post('/chat', { message: text });\n"
        "        if (!r.ok) {\n"
        "          appendMessage('buddy', 'Errore: ' + r.status, 'neutral');\n"
        "          setChatInputEnabled(true);\n"
        "        }\n"
        "      } catch(e) {\n"
        "        appendMessage('buddy', 'Errore: ' + e, 'neutral');\n"
        "        setChatInputEnabled(true);\n"
        "      }\n"
        "    }\n"
        "\n"
        "    // --- TTS ---\n"
        "    async function sendSpeak() {\n"
        "      const text = document.getElementById('tts-text').value.trim();\n"
        "      if (!text) return;\n"
        "      setStatus('status', 'Sintesi in corso\u2026', '');\n"
        "      try {\n"
        "        const r = await post('/speak', { text });\n"
        "        if (r.ok) {\n"
        "          const blob = await r.blob();\n"
        "          const url = URL.createObjectURL(blob);\n"
        "          const audio = new Audio(url);\n"
        "          audio.play();\n"
        "          audio.onended = () => URL.revokeObjectURL(url);\n"
        "          setStatus('status', 'Riproduzione in corso', 'ok');\n"
        "        } else {\n"
        "          setStatus('status', 'Errore TTS: ' + r.status, 'err');\n"
        "        }\n"
        "      } catch(e) { setStatus('status', 'Errore: ' + e, 'err'); }\n"
        "    }\n"
        "\n"
        "    // --- keyboard shortcuts ---\n"
        "    document.getElementById('chat-input').addEventListener('keydown', e => { if (e.key==='Enter') sendChat(); });\n"
        "    document.getElementById('tts-text').addEventListener('keydown', e => { if (e.key==='Enter') sendSpeak(); });\n"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )


_HTML = _build_html()


def _framebuffer_to_png(fb: bytearray) -> bytes:
    """Convert SSD1306 framebuffer (128×64, 1bpp column-major) to PNG bytes.

    Renders lit pixels as Matrix green (#39FF14) on a black background.
    """
    try:
        from PIL import Image
    except ImportError:
        # Fallback: 1×1 black PNG
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x00"
            b"\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xde\xfc\x00"
            b"\x00\x00\x00IEND\xaeB`\x82"
        )

    # Matrix neon green on black
    GREEN = (57, 255, 20)  # #39FF14

    img = Image.new("RGB", (128, 64), (0, 0, 0))
    pixels = img.load()

    for x in range(128):
        for page in range(8):
            byte = fb[x + page * 128]
            for bit in range(8):
                y = page * 8 + bit
                if (byte >> bit) & 1:
                    pixels[x, y] = GREEN

    img = img.resize((128 * _SCALE, 64 * _SCALE), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._respond(200, "text/html; charset=utf-8", _HTML.encode())
        elif path == "/display.png":
            global _display_png_cache, _display_png_time
            now = time.time()
            if (
                _display_png_cache is None
                or (now - _display_png_time) > _display_png_ttl
            ):
                fb = (
                    _state["display"].get_framebuffer()
                    if _state["display"]
                    else bytearray(1024)
                )
                _display_png_cache = _framebuffer_to_png(fb)
                _display_png_time = now
            self._respond(200, "image/png", _display_png_cache)
        elif path == "/updates":
            self._handle_poll_updates()
        else:
            self._respond(404, "text/plain", b"not found")

    def _handle_poll_updates(self):
        """Return all pending updates for polling clients."""
        updates = []
        try:
            while True:
                updates.append(_update_queue.get_nowait())
        except queue.Empty:
            pass
        self._respond(200, "application/json", json.dumps(updates).encode())

    def _handle_sse(self):
        """Server-Sent Events for real-time updates."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = queue.Queue()
        with _sse_lock:
            _sse_clients.append(q)

        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    msg = f"data: {json.dumps(data)}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    heartbeat = b'data: {"type":"ping"}\n\n'
                    self.wfile.write(heartbeat)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/expression":
            name = body.get("name", "neutral")
            expressions = _state.get("expressions")
            if expressions:
                threading.Thread(
                    target=expressions.show_expression,
                    args=(name,),
                    daemon=True,
                ).start()
            _broadcast({"type": "expression", "name": name})
            self._respond(200, "application/json", b'{"ok":true}')

        elif self.path == "/speak":
            text = body.get("text", "")
            tts_url = _state.get("tts_url")
            if not text or not tts_url:
                self._respond(503, "text/plain", b"TTS not configured")
                return
            try:
                data = json.dumps({"text": text}).encode()
                req = urllib.request.Request(
                    f"{tts_url.rstrip('/')}/synthesize",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    wav_bytes = resp.read()
                self._respond(200, "audio/wav", wav_bytes)
            except Exception as e:
                logger.warning(f"TTS proxy failed: {e}")
                self._respond(502, "text/plain", str(e).encode())

        elif self.path == "/chat":
            message = body.get("message", "").strip()
            if not message:
                self._respond(400, "text/plain", b"Empty message")
                return

            _broadcast({"type": "expression", "name": "thinking"})
            _broadcast({"type": "thinking", "text": "Sto pensando..."})

            callback = _state.get("chat_callback")
            if callback:

                def respond(response_text: str, expression: str = "neutral"):
                    _broadcast(
                        {
                            "type": "chat_response",
                            "text": response_text,
                            "expression": expression,
                        }
                    )
                    _broadcast({"type": "expression", "name": expression})

                def run_callback():
                    try:
                        callback(message, respond)
                    except Exception as e:
                        logger.error(f"Chat callback error: {e}")
                        _broadcast(
                            {
                                "type": "chat_response",
                                "text": f"Errore: {e}",
                                "expression": "confused",
                            }
                        )

                threading.Thread(target=run_callback, daemon=True).start()
            else:
                _broadcast(
                    {
                        "type": "chat_response",
                        "text": "Chat non disponibile - avvia Fresh Buddy",
                        "expression": "neutral",
                    }
                )
            self._respond(200, "application/json", b'{"ok":true}')

        else:
            self._respond(404, "text/plain", b"not found")

    def _respond(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # silence access log
        pass


def put_response(text: str):
    """Store the latest command response so the browser can poll it."""
    _last_response["text"] = text
    _last_response["seq"] += 1


def _broadcast(data: dict):
    """Broadcast data to all SSE clients and update polling queue."""
    global _update_seq
    with _sse_lock:
        for q in list(_sse_clients):
            try:
                q.put_nowait(data)
            except queue.Full:
                pass
    try:
        _update_queue.put_nowait(
            {
                "type": data.get("type"),
                "name": data.get("name"),
                "text": data.get("text"),
                "expression": data.get("expression"),
                "seq": _update_seq,
            }
        )
        _update_seq += 1
    except queue.Full:
        pass


def configure(expressions=None, tts_url: str = None, chat_callback=None):
    """Call this after all components are ready to enable interactive endpoints."""
    if expressions is not None:
        _state["expressions"] = expressions
    if tts_url is not None:
        _state["tts_url"] = tts_url
    if chat_callback is not None:
        _state["chat_callback"] = chat_callback


def broadcast_expression(name: str):
    """Broadcast expression change to all SSE clients."""
    _broadcast({"type": "expression", "name": name})


def get_command_queue() -> queue.Queue:
    """Return the queue that the main loop should drain for simulated commands."""
    return _state["command_queue"]


def start_preview_server(display, port: int = 8088):
    """Start the preview HTTP server in a background daemon thread."""
    _state["display"] = display
    server = HTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Dev console running at http://localhost:{port}/")
    return server
