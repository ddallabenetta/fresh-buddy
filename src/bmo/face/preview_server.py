"""OLED Display Preview Server — development only.

Interactive dashboard for the 800×480 BMO face display:
  GET  /             → HTML dev console (full chat + debug controls)
  GET  /display.png  → current framebuffer as PNG (?scheme=<name>)
  GET  /updates      → poll queue for real-time expression/chat updates
  GET  /settings     → current debug settings as JSON
  POST /expression   → {"name": "happy"} — trigger an expression
  POST /speak        → {"text": "..."} — proxy to TTS, returns audio/wav
  POST /chat         → {"message": "..."} — send chat message, returns response
  POST /settings     → {"transition_ms":400,"color_scheme":"cyan",...}
  POST /glitch       → trigger a glitch test effect
"""

import io
import json
import logging
import queue
import random
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

# ── display dimensions ────────────────────────────────────────────
W, H = 800, 480   # canvas resolution

# ── color themes ────────────────────────────────────────────────
_COLOR_SCHEMES = {
    "green":   (57,  255, 20),   # Matrix neon green  #39FF14
    "cyan":    (0,   255, 255),  # Cyan               #00FFFF
    "magenta": (255, 0,   255),  # Magenta            #FF00FF
    "amber":   (255, 176, 0),    # Amber              #FFB000
}
_DEFAULT_SCHEME = "green"

# Shared state — populated by configure() after all components are ready
_state: dict = {
    "display":          None,
    "expressions":      None,
    "tts_url":          None,
    "command_queue":    queue.Queue(),
    "chat_callback":    None,
    # ── debug settings ──────────────────────────────────────────
    "transition_ms":    300,
    "color_scheme":     _DEFAULT_SCHEME,
    "speed_multiplier": 1.0,
    "scanlines":        True,
    "glow":             True,
    # ── glitch state ────────────────────────────────────────────
    "glitch_until":     0.0,
}

_last_response: dict = {"text": None, "seq": 0}

_sse_clients: list = []
_sse_lock = threading.Lock()

_update_queue: queue.Queue = queue.Queue()
_update_seq: int = 0

_display_png_cache: bytes = None
_display_png_time:  float = 0
_display_png_ttl:   float = 0.1   # 100 ms — fast enough for 30 fps

_EXPRESSIONS = [
    "neutral", "happy", "sad", "excited", "confused",
    "thinking", "listening", "speaking", "recording", "sleeping",
]


def _build_html() -> str:
    """Build the dev console HTML with full chat interface and debug controls."""
    expr_buttons = "\n      ".join(
        f'<button class="expr-btn" id="expr-{e}" onclick="sendExpression(\'{e}\')">{e}</button>'
        for e in _EXPRESSIONS
    )
    scheme_opts = "\n            ".join(
        f'<option value="{s}">{s.title()}</option>'
        for s in _COLOR_SCHEMES
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Fresh Buddy — Dev Console (800×480)</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0a0a0a; color: #ddd;
      font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
      display: flex; flex-direction: column; align-items: center;
      padding: 16px; gap: 16px;
      min-height: 100vh;
    }}
    h1 {{ color: #fff; font-size: 1rem; letter-spacing: 2px; text-transform: uppercase; }}
    h2 {{ font-size: .7rem; color: #888; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }}
    .top-bar {{ display: flex; gap: 16px; width: 100%; max-width: 960px; align-items: flex-start; flex-wrap: wrap; }}
    #oled-wrap {{ display: flex; flex-direction: column; align-items: center; gap: 4px; flex-shrink: 0; }}
    #fb-container {{ position: relative; display: inline-block; }}
    #fb {{ image-rendering: pixelated; border: 2px solid #333; border-radius: 4px; display: block; }}
    #scanlines {{
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background: repeating-linear-gradient(
        0deg, transparent, transparent 2px, rgba(0,0,0,0.28) 2px, rgba(0,0,0,0.28) 4px
      );
      pointer-events: none; border-radius: 4px; display: none;
    }}
    #oled-wrap p {{ color: #444; font-size: 10px; }}
    .fps-badge {{
      font-size: 10px; color: #22c55e; background: #0d1a0d;
      border: 1px solid #1b5e20; border-radius: 4px; padding: 2px 6px;
      font-variant-numeric: tabular-nums;
    }}
    .card {{
      background: #141414; border: 1px solid #2a2a2a; border-radius: 8px;
      padding: 12px; flex: 1;
    }}
    #chat-container {{ display: flex; flex-direction: column; height: 320px; }}
    #chat-history {{
      flex: 1; overflow-y: auto; border: 1px solid #2a2a2a; border-radius: 4px;
      padding: 10px; background: #0d0d0d; display: flex; flex-direction: column; gap: 8px;
    }}
    .msg {{ max-width: 85%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.4; }}
    .msg.user {{ align-self: flex-end; background: #1565c0; color: #fff; border-bottom-right-radius: 2px; }}
    .msg.buddy {{ align-self: flex-start; background: #1a1a1a; border: 1px solid #333; color: #ccc; border-bottom-left-radius: 2px; }}
    .msg.buddy.thinking {{ border-color: #f59e0b; }}
    .msg.buddy.speaking {{ border-color: #22c55e; }}
    .msg.buddy .expr-tag {{ font-size: 10px; color: #888; margin-top: 4px; display: block; }}
    #chat-input-row {{ display: flex; gap: 8px; margin-top: 10px; }}
    #chat-input {{
      flex: 1; background: #1a1a1a; border: 1px solid #333; color: #eee;
      border-radius: 20px; padding: 10px 16px; font-family: inherit; font-size: 13px;
    }}
    #chat-input:focus {{ outline: none; border-color: #555; }}
    #chat-input:disabled {{ opacity: 0.5; }}
    .send-btn {{
      background: #22c55e; border: none; color: #fff; border-radius: 50%;
      width: 40px; height: 40px; cursor: pointer; font-size: 18px;
      display: flex; align-items: center; justify-content: center;
    }}
    .send-btn:hover {{ background: #16a34a; }}
    .send-btn:disabled {{ background: #333; cursor: not-allowed; }}
    .expr-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; }}
    .expr-btn {{
      background: #1a1a1a; border: 1px solid #333; color: #888;
      border-radius: 4px; padding: 5px 3px; font-size: 10px;
      cursor: pointer; text-align: center; transition: all .15s;
    }}
    .expr-btn:hover {{ background: #2e7d32; color: #fff; border-color: #388e3c; }}
    .expr-btn.active {{ background: #1b5e20; color: #a5d6a7; border-color: #2e7d32; }}
    .row {{ display: flex; gap: 8px; margin-top: 8px; align-items: center; flex-wrap: wrap; }}
    input[type=text], input[type=range], select {{
      background: #1a1a1a; border: 1px solid #333; color: #eee;
      border-radius: 4px; padding: 8px 10px; font-family: inherit; font-size: 12px;
    }}
    input[type=text] {{ flex: 1; }}
    input[type=text]:focus, select:focus {{ outline: none; border-color: #555; }}
    input[type=range] {{ cursor: pointer; padding: 4px 6px; }}
    select {{ cursor: pointer; }}
    .btn {{
      background: #1565c0; border: none; color: #fff;
      border-radius: 4px; padding: 8px 14px; font-family: inherit;
      font-size: 11px; cursor: pointer; white-space: nowrap; transition: background .15s;
    }}
    .btn:hover {{ background: #1976d2; }}
    .btn.green {{ background: #2e7d32; }}
    .btn.green:hover {{ background: #388e3c; }}
    .btn.amber {{ background: #b45309; }}
    .btn.amber:hover {{ background: #d97706; }}
    .btn.red {{ background: #b91c1c; }}
    .btn.red:hover {{ background: #dc2626; }}
    .btn.toggle {{ background: #333; }}
    .btn.toggle.on {{ background: #0f766e; border-color: #14b8a6; }}
    .btn.toggle:hover {{ background: #444; }}
    .btn.toggle.on:hover {{ background: #0d9488; }}
    #status {{ font-size: 10px; color: #555; min-height: 14px; margin-top: 6px; transition: color .3s; }}
    #status.ok  {{ color: #66bb6a; }}
    #status.err {{ color: #ef5350; }}
    .card-mini {{ background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; padding: 10px; }}
    .mini-row {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    label {{ font-size: 11px; color: #666; white-space: nowrap; }}
    .slider-val {{ font-size: 11px; color: #aaa; min-width: 42px; text-align: right; }}
    .debug-section {{ display: flex; flex-direction: column; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #222; }}
  </style>
</head>
<body>
  <h1>Fresh Buddy — Dev Console (800×480)</h1>

  <div class="top-bar">

    <div id="oled-wrap" class="card">
      <h2>Display <span class="fps-badge" id="fps-badge">– fps</span></h2>
      <div id="fb-container">
        <img id="fb" src="/display.png" width="{W}" height="{H}" alt="framebuffer">
        <div id="scanlines"></div>
      </div>
      <p>auto-refresh</p>

      <div class="expr-grid" style="margin-top:10px;">
        {expr_buttons}
      </div>

      <div class="debug-section" style="width:100%;">

        <div class="row">
          <label>Transition</label>
          <input type="range" id="transition-slider" min="100" max="1000" step="50" value="300"
                 oninput="updateSliderLabel('transition-slider','transition-val','ms'); applySettings()">
          <span class="slider-val" id="transition-val">300ms</span>
        </div>

        <div class="row">
          <label>Speed</label>
          <select id="speed-select" onchange="applySettings()">
            <option value="0.5">0.5×</option>
            <option value="1" selected>1×</option>
            <option value="2">2×</option>
          </select>
          <label style="margin-left:8px;">Scheme</label>
          <select id="scheme-select" onchange="applySettings()">
            {scheme_opts}
          </select>
        </div>

        <div class="row">
          <button class="btn toggle on" id="scanline-btn" onclick="toggleScanlines()">Scanlines</button>
          <button class="btn toggle on" id="glow-btn" onclick="toggleGlow()">Glow</button>
          <button class="btn red" onclick="triggerGlitch()">⚡ Glitch</button>
        </div>

      </div>
    </div>

    <div id="chat-container" class="card">
      <h2>Chat</h2>
      <div id="chat-history"></div>
      <div id="chat-input-row">
        <input id="chat-input" type="text" placeholder="Send a message..." autocomplete="off">
        <button class="send-btn" id="send-btn" onclick="sendChat()">➤</button>
      </div>
    </div>

  </div>

  <div class="card-mini" style="width:100%;max-width:960px;">
    <div class="mini-row">
      <input id="tts-text" type="text" placeholder="Test TTS..." value="Hello!">
      <button class="btn green" onclick="sendSpeak()">Speak</button>
    </div>
    <div id="status"></div>
  </div>

  <script>
    // ── display refresh & FPS counter ──────────────────────────
    let _frameCount = 0;
    let _fpsTs = Date.now();
    let _currentScheme = 'green';
    let _refreshMs = 100;

    function refreshDisplay() {{
      const img = document.getElementById('fb');
      img.onload = () => {{
        _frameCount++;
        const now = Date.now();
        const elapsed = (now - _fpsTs) / 1000;
        if (elapsed >= 1) {{
          const fps = (_frameCount / elapsed).toFixed(1);
          document.getElementById('fps-badge').textContent = fps + ' fps';
          _frameCount = 0;
          _fpsTs = now;
        }}
      }};
      img.src = '/display.png?scheme=' + _currentScheme + '&t=' + Date.now();
    }}

    function startRefreshLoop() {{
      setInterval(refreshDisplay, _refreshMs);
    }}
    startRefreshLoop();

    // ── settings ───────────────────────────────────────────────
    function updateSliderLabel(sliderId, labelId, suffix) {{
      const v = document.getElementById(sliderId).value;
      document.getElementById(labelId).textContent = v + suffix;
    }}

    async function applySettings() {{
      const tm  = parseInt(document.getElementById('transition-slider').value);
      const sp  = parseFloat(document.getElementById('speed-select').value);
      const sch = document.getElementById('scheme-select').value;
      _currentScheme = sch;
      _refreshMs = Math.round(100 / sp);
      await post('/settings', {{ transition_ms: tm, speed_multiplier: sp, color_scheme: sch }});
    }}

    function toggleScanlines() {{
      const btn = document.getElementById('scanline-btn');
      const sl  = document.getElementById('scanlines');
      const isOn = btn.classList.contains('on');
      if (isOn) {{
        btn.classList.remove('on');
        sl.style.display = 'none';
        post('/settings', {{ scanlines: false }});
      }} else {{
        btn.classList.add('on');
        sl.style.display = 'block';
        post('/settings', {{ scanlines: true }});
      }}
    }}

    function toggleGlow() {{
      const btn = document.getElementById('glow-btn');
      const isOn = btn.classList.contains('on');
      if (isOn) {{
        btn.classList.remove('on');
        post('/settings', {{ glow: false }});
      }} else {{
        btn.classList.add('on');
        post('/settings', {{ glow: true }});
      }}
    }}

    async function triggerGlitch() {{
      await post('/glitch', {{}});
    }}

    // ── polling for updates ─────────────────────────────────────
    function processUpdate(data) {{
      if (!data || !data.type) return;
      if (data.type === 'expression') {{
        document.querySelectorAll('.expr-btn').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById('expr-' + data.name);
        if (btn) btn.classList.add('active');
      }} else if (data.type === 'chat_response') {{
        appendMessage('buddy', data.text, data.expression);
        setChatInputEnabled(true);
        autoPlayTTS(data.text);
      }} else if (data.type === 'thinking') {{
        appendMessage('buddy', data.text, 'thinking');
      }}
    }}
    async function pollUpdates() {{
      try {{
        const r = await fetch('/updates');
        if (r.ok) {{
          const updates = await r.json();
          for (const data of updates) processUpdate(data);
        }}
      }} catch(err) {{}}
    }}
    setInterval(pollUpdates, 800);

    // ── helpers ─────────────────────────────────────────────────
    function setStatus(id, msg, cls) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = msg;
      el.className = cls || '';
    }}

    function setChatInputEnabled(enabled) {{
      const inp = document.getElementById('chat-input');
      const btn = document.getElementById('send-btn');
      if (inp) inp.disabled = !enabled;
      if (btn) btn.disabled = !enabled;
    }}

    function appendMessage(role, text, expr) {{
      const history = document.getElementById('chat-history');
      if (!history || !text) return;
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      if (expr) div.className += ' ' + expr;
      div.textContent = text;
      if (role === 'buddy' && expr) {{
        const tag = document.createElement('span');
        tag.className = 'expr-tag';
        tag.textContent = expr;
        div.appendChild(tag);
      }}
      history.appendChild(div);
      history.scrollTop = history.scrollHeight;
    }}

    async function post(url, body) {{
      return fetch(url, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
      }});
    }}

    async function autoPlayTTS(text) {{
      if (!text) return;
      try {{
        const r = await post('/speak', {{ text }});
        if (r.ok) {{
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.play();
          audio.onended = () => URL.revokeObjectURL(url);
        }}
      }} catch(e) {{}}
    }}

    // ── expressions ─────────────────────────────────────────────
    async function sendExpression(name) {{
      document.querySelectorAll('.expr-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('expr-' + name).classList.add('active');
      await post('/expression', {{ name }});
    }}

    // ── chat ─────────────────────────────────────────────────────
    async function sendChat() {{
      const inp  = document.getElementById('chat-input');
      const text = inp.value.trim();
      if (!text) return;
      appendMessage('user', text);
      inp.value = '';
      setChatInputEnabled(false);
      try {{
        const r = await post('/chat', {{ message: text }});
        if (!r.ok) {{
          appendMessage('buddy', 'Error: ' + r.status, 'neutral');
          setChatInputEnabled(true);
        }}
      }} catch(e) {{
        appendMessage('buddy', 'Error: ' + e, 'neutral');
        setChatInputEnabled(true);
      }}
    }}

    // ── TTS ──────────────────────────────────────────────────────
    async function sendSpeak() {{
      const text = document.getElementById('tts-text').value.trim();
      if (!text) return;
      setStatus('status', 'Synthesising…', '');
      try {{
        const r = await post('/speak', {{ text }});
        if (r.ok) {{
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.play();
          audio.onended = () => URL.revokeObjectURL(url);
          setStatus('status', 'Playing…', 'ok');
        }} else {{
          setStatus('status', 'TTS error: ' + r.status, 'err');
        }}
      }} catch(e) {{ setStatus('status', 'Error: ' + e, 'err'); }}
    }}

    // ── keyboard shortcuts ───────────────────────────────────────
    document.getElementById('chat-input').addEventListener('keydown', e => {{ if (e.key==='Enter') sendChat(); }});
    document.getElementById('tts-text').addEventListener('keydown', e => {{ if (e.key==='Enter') sendSpeak(); }});
  </script>
</body>
</html>
"""


_HTML: str = _build_html()


def _framebuffer_to_png(fb: bytearray, scheme: str = _DEFAULT_SCHEME) -> bytes:
    """Convert an 800×480 bytearray (row-major, lit-pixel=255) to PNG.

    Reads directly from ``display.get_framebuffer()`` which provides a flat
    bytearray of the full canvas.  Pixel value > 0 is treated as a lit pixel.

    ``scheme`` selects the colour for lit pixels (green / cyan / magenta / amber).
    When the glitch effect is active, ~12 % of rows are XORed with a random value.
    """
    try:
        from PIL import Image
    except ImportError:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x00"
            b"\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xde\xfc\x00"
            b"\x00\x00\x00IEND\xaeB`\x82"
        )

    color          = _COLOR_SCHEMES.get(scheme, _COLOR_SCHEMES[_DEFAULT_SCHEME])
    glitch_active  = time.time() < _state["glitch_until"]

    data = bytearray(W * H)
    data[:min(len(fb), W * H)] = fb[:min(len(fb), W * H)]

    if glitch_active:
        for row_idx in range(H):
            if random.random() < 0.12:
                xor_val = random.randint(1, 255)
                row_start = row_idx * W
                for col_idx in range(W):
                    data[row_start + col_idx] ^= xor_val

    img = Image.frombytes("L", (W, H), bytes(data))

    if color != (255, 255, 255):
        try:
            import numpy as np
            lum = np.frombuffer(bytes(data), dtype=np.uint8).reshape(H, W)
            rgb = np.zeros((H, W, 3), dtype=np.uint8)
            for idx, channel in enumerate(color):
                rgb[:, :, idx] = (lum.astype(np.uint16) * channel // 255).astype(np.uint8)
            img = Image.fromarray(rgb, "RGB")
        except Exception:
            rgb_img = Image.new("RGB", (W, H), (0, 0, 0))
            pixs = img.load()
            for y in range(H):
                for x in range(W):
                    val = pixs[x, y]
                    if val:
                        rgb_img.putpixel((x, y), tuple(int(c * val / 255) for c in color))
            img = rgb_img
    else:
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parts  = self.path.split("?", 1)
        path   = parts[0]
        qs     = parts[1] if len(parts) > 1 else ""
        params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)

        if path in ("/", "/index.html"):
            self._respond(200, "text/html; charset=utf-8", _HTML.encode())

        elif path == "/display.png":
            global _display_png_cache, _display_png_time
            scheme        = params.get("scheme", _state["color_scheme"])
            now           = time.time()
            glitch_active = now < _state["glitch_until"]
            if (
                _display_png_cache is None
                or (now - _display_png_time) > _display_png_ttl
                or glitch_active
            ):
                fb = (
                    _state["display"].get_framebuffer()
                    if _state["display"]
                    else bytearray(W * H)
                )
                _display_png_cache = _framebuffer_to_png(fb, scheme)
                _display_png_time   = now
            self._respond(200, "image/png", _display_png_cache)

        elif path == "/updates":
            self._handle_poll_updates()

        elif path == "/settings":
            self._respond(
                200, "application/json",
                json.dumps({
                    "transition_ms":    _state["transition_ms"],
                    "color_scheme":     _state["color_scheme"],
                    "speed_multiplier": _state["speed_multiplier"],
                    "scanlines":        _state["scanlines"],
                    "glow":             _state["glow"],
                }).encode()
            )

        else:
            self._respond(404, "text/plain", b"not found")

    def _handle_poll_updates(self):
        updates = []
        try:
            while True:
                updates.append(_update_queue.get_nowait())
        except queue.Empty:
            pass
        self._respond(200, "application/json", json.dumps(updates).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

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
            text    = body.get("text", "")
            tts_url = _state.get("tts_url")
            if not text or not tts_url:
                self._respond(503, "text/plain", b"TTS not configured")
                return
            try:
                data = json.dumps({"text": text}).encode()
                req  = urllib.request.Request(
                    f"{tts_url.rstrip('/')}/synthesize",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    wav_bytes = resp.read()
                self._respond(200, "audio/wav", wav_bytes)
            except Exception as e:
                logger.warning("TTS proxy failed: %s", e)
                self._respond(502, "text/plain", str(e).encode())

        elif self.path == "/chat":
            message = body.get("message", "").strip()
            if not message:
                self._respond(400, "text/plain", b"Empty message")
                return

            _broadcast({"type": "expression", "name": "thinking"})
            _broadcast({"type": "thinking",   "text": "Thinking…"})

            callback = _state.get("chat_callback")
            if callback:
                def respond(response_text: str, expression: str = "neutral"):
                    _broadcast({
                        "type":       "chat_response",
                        "text":       response_text,
                        "expression": expression,
                    })
                    _broadcast({"type": "expression", "name": expression})

                def run_callback():
                    try:
                        callback(message, respond)
                    except Exception as e:
                        logger.error("Chat callback error: %s", e)
                        _broadcast({
                            "type":       "chat_response",
                            "text":       f"Error: {e}",
                            "expression": "confused",
                        })

                threading.Thread(target=run_callback, daemon=True).start()
            else:
                _broadcast({
                    "type":       "chat_response",
                    "text":       "Chat unavailable — start Fresh Buddy first",
                    "expression": "neutral",
                })
            self._respond(200, "application/json", b'{"ok":true}')

        elif self.path == "/settings":
            allowed = {"transition_ms", "color_scheme", "speed_multiplier", "scanlines", "glow"}
            for key in allowed:
                if key in body:
                    val = body[key]
                    if key == "transition_ms":
                        val = max(100, min(1000, int(val)))
                    elif key == "color_scheme":
                        val = val if val in _COLOR_SCHEMES else _DEFAULT_SCHEME
                    elif key == "speed_multiplier":
                        val = float(val)
                    elif key == "scanlines":
                        val = bool(val)
                    elif key == "glow":
                        val = bool(val)
                    _state[key] = val
            expressions = _state.get("expressions")
            if expressions and hasattr(expressions, "set_render_options"):
                expressions.set_render_options(
                    transition_ms=_state["transition_ms"],
                    speed_multiplier=_state["speed_multiplier"],
                    scanlines=_state["scanlines"],
                    glow=_state["glow"],
                )
            self._respond(200, "application/json", b'{"ok":true}')

        elif self.path == "/glitch":
            _state["glitch_until"] = time.time() + 1.5
            _broadcast({"type": "expression", "name": "confused"})
            self._respond(200, "application/json", b'{"ok":true,"duration_ms":1500}')

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
    _last_response["text"] = text
    _last_response["seq"] += 1


def _broadcast(data: dict):
    global _update_seq
    with _sse_lock:
        for q in list(_sse_clients):
            try:
                q.put_nowait(data)
            except queue.Full:
                pass
    try:
        _update_queue.put_nowait({
            "type":       data.get("type"),
            "name":       data.get("name"),
            "text":       data.get("text"),
            "expression": data.get("expression"),
            "seq":        _update_seq,
        })
        _update_seq += 1
    except queue.Full:
        pass


def configure(expressions=None, tts_url: str = None, chat_callback=None):
    if expressions is not None:
        _state["expressions"] = expressions
        if hasattr(expressions, "set_render_options"):
            expressions.set_render_options(
                transition_ms=_state["transition_ms"],
                speed_multiplier=_state["speed_multiplier"],
                scanlines=_state["scanlines"],
                glow=_state["glow"],
            )
    if tts_url is not None:
        _state["tts_url"] = tts_url
    if chat_callback is not None:
        _state["chat_callback"] = chat_callback


def broadcast_expression(name: str):
    _broadcast({"type": "expression", "name": name})


def get_command_queue() -> queue.Queue:
    return _state["command_queue"]


def start_preview_server(display, port: int = 8088):
    _state["display"] = display
    server = HTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Dev console running at http://localhost:{port}/")
    return server
