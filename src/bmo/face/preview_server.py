"""OLED Display Preview Server — development only.

Interactive dashboard:
  GET  /             → HTML dev console
  GET  /display.png  → current framebuffer as PNG (auto-refreshed)
  GET  /response     → {"text": "...", "seq": N} last command response (poll)
  POST /expression   → {"name": "happy"} — trigger an expression
  POST /speak        → {"text": "..."} — proxy to TTS, returns audio/wav
  POST /command      → {"text": "..."} — inject a simulated voice command
"""

import io
import json
import logging
import queue
import threading
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
}

# Last response from a simulated command — polled by the browser
_last_response: dict = {"text": None, "seq": 0}

_EXPRESSIONS = [
    "neutral", "happy", "sad", "excited",
    "confused", "thinking", "listening", "speaking",
    "recording", "sleeping",
]

def _build_html() -> str:
    """Build the dev console HTML. Uses simple replacement to avoid .format() clashes with CSS braces."""
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
        "      background: #111; color: #ddd;\n"
        "      font-family: 'Courier New', monospace;\n"
        "      display: flex; flex-direction: column; align-items: center;\n"
        "      padding: 24px 16px; gap: 24px;\n"
        "    }\n"
        "    h1 { color: #fff; font-size: 1.1rem; letter-spacing: 2px; text-transform: uppercase; }\n"
        "    h2 { font-size: .8rem; color: #888; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; }\n"
        "    #oled-wrap { display: flex; flex-direction: column; align-items: center; gap: 6px; }\n"
        "    #fb { image-rendering: pixelated; border: 2px solid #333; }\n"
        "    #oled-wrap p { color: #444; font-size: 11px; }\n"
        "    .card {\n"
        "      background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;\n"
        "      padding: 16px; width: 100%; max-width: 560px;\n"
        "    }\n"
        "    .expr-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }\n"
        "    .expr-btn {\n"
        "      background: #222; border: 1px solid #333; color: #aaa;\n"
        "      border-radius: 4px; padding: 6px 4px; font-size: 11px;\n"
        "      cursor: pointer; text-align: center; transition: background .15s, color .15s;\n"
        "    }\n"
        "    .expr-btn:hover { background: #2e7d32; color: #fff; border-color: #388e3c; }\n"
        "    .expr-btn.active { background: #1b5e20; color: #a5d6a7; border-color: #2e7d32; }\n"
        "    .row { display: flex; gap: 8px; margin-top: 8px; }\n"
        "    input[type=text] {\n"
        "      flex: 1; background: #222; border: 1px solid #333; color: #eee;\n"
        "      border-radius: 4px; padding: 8px 10px; font-family: inherit; font-size: 13px;\n"
        "    }\n"
        "    input[type=text]:focus { outline: none; border-color: #555; }\n"
        "    .btn {\n"
        "      background: #1565c0; border: none; color: #fff;\n"
        "      border-radius: 4px; padding: 8px 14px; font-family: inherit;\n"
        "      font-size: 12px; cursor: pointer; white-space: nowrap; transition: background .15s;\n"
        "    }\n"
        "    .btn:hover { background: #1976d2; }\n"
        "    .btn.green { background: #2e7d32; }\n"
        "    .btn.green:hover { background: #388e3c; }\n"
        "    #status { font-size: 11px; color: #555; min-height: 16px; margin-top: 8px; transition: color .3s; }\n"
        "    #status.ok  { color: #66bb6a; }\n"
        "    #status.err { color: #ef5350; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Fresh Buddy \u2014 Dev Console</h1>\n"
        '\n  <div id="oled-wrap" class="card">\n'
        "    <h2>Display (simulation)</h2>\n"
        f'    <img id="fb" src="/display.png" width="{w}" height="{h}" alt="framebuffer">\n'
        "    <p>auto-refresh 1 s</p>\n"
        "  </div>\n"
        '\n  <div class="card">\n'
        "    <h2>Espressioni</h2>\n"
        '    <div class="expr-grid">\n'
        f"      {expr_buttons}\n"
        "    </div>\n"
        "  </div>\n"
        '\n  <div class="card">\n'
        "    <h2>Test TTS</h2>\n"
        '    <div class="row">\n'
        '      <input id="tts-text" type="text" placeholder="Testo da sintetizzare..." value="Ciao! Sono Fresh Buddy.">\n'
        '      <button class="btn green" onclick="sendSpeak()">Parla</button>\n'
        "    </div>\n"
        '    <div id="status"></div>\n'
        "  </div>\n"
        '\n  <div class="card">\n'
        "    <h2>Simula comando vocale</h2>\n"
        '    <div class="row">\n'
        '      <input id="cmd-text" type="text" placeholder="es. riassumi la riunione...">\n'
        '      <button class="btn" onclick="sendCommand()">Invia</button>\n'
        "    </div>\n"
        '    <div id="cmd-status"></div>\n'
        "  </div>\n"
        '\n  <div class="card">\n'
        "    <h2>Ultima risposta</h2>\n"
        '    <div id="response-box" style="white-space:pre-wrap;font-size:12px;color:#ccc;min-height:32px;">\u2014</div>\n'
        "  </div>\n"
        "\n  <script>\n"
        "    // --- display refresh ---\n"
        "    setInterval(() => {\n"
        "      const img = document.getElementById('fb');\n"
        "      img.src = '/display.png?' + Date.now();\n"
        "    }, 1000);\n"
        "\n"
        "    // --- helpers ---\n"
        "    function setStatus(id, msg, cls) {\n"
        "      const el = document.getElementById(id);\n"
        "      if (!el) return;\n"
        "      el.textContent = msg;\n"
        "      el.className = cls || '';\n"
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
        "    // --- expressions ---\n"
        "    async function sendExpression(name) {\n"
        "      document.querySelectorAll('.expr-btn').forEach(b => b.classList.remove('active'));\n"
        "      document.getElementById('expr-' + name).classList.add('active');\n"
        "      await post('/expression', { name });\n"
        "    }\n"
        "\n"
        "    // --- TTS: proxy returns audio/wav, play in browser ---\n"
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
        "    // --- simulated voice command ---\n"
        "    async function sendCommand() {\n"
        "      const text = document.getElementById('cmd-text').value.trim();\n"
        "      if (!text) return;\n"
        "      setStatus('cmd-status', 'In attesa di risposta\u2026', '');\n"
        "      await post('/command', { text });\n"
        "      document.getElementById('cmd-text').value = '';\n"
        "    }\n"
        "\n"
        "    // --- poll for command responses ---\n"
        "    let _lastSeq = 0;\n"
        "    async function pollResponse() {\n"
        "      try {\n"
        "        const r = await fetch('/response');\n"
        "        const data = await r.json();\n"
        "        if (data.seq > _lastSeq && data.text) {\n"
        "          _lastSeq = data.seq;\n"
        "          document.getElementById('response-box').textContent = data.text;\n"
        "          setStatus('cmd-status', 'Risposta ricevuta', 'ok');\n"
        "        }\n"
        "      } catch(e) {}\n"
        "    }\n"
        "    setInterval(pollResponse, 1500);\n"
        "\n"
        "    // --- keyboard shortcuts ---\n"
        "    document.getElementById('tts-text').addEventListener('keydown', e => { if (e.key==='Enter') sendSpeak(); });\n"
        "    document.getElementById('cmd-text').addEventListener('keydown', e => { if (e.key==='Enter') sendCommand(); });\n"
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
    GREEN = (57, 255, 20)   # #39FF14

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
            fb = (_state["display"].get_framebuffer()
                  if _state["display"] else bytearray(1024))
            self._respond(200, "image/png", _framebuffer_to_png(fb))
        elif path == "/response":
            data = json.dumps(_last_response).encode()
            self._respond(200, "application/json", data)
        else:
            self._respond(404, "text/plain", b"not found")

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
            self._respond(200, "application/json", b'{"ok":true}')

        elif self.path == "/speak":
            # Proxy to TTS service synchronously — return WAV bytes to browser
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

        elif self.path == "/command":
            text = body.get("text", "").strip()
            if text:
                _state["command_queue"].put(text)
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


def configure(expressions=None, tts_url: str = None):
    """Call this after all components are ready to enable interactive endpoints."""
    if expressions is not None:
        _state["expressions"] = expressions
    if tts_url is not None:
        _state["tts_url"] = tts_url


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
