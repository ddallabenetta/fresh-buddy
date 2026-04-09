"""Expression Engine for Fresh Buddy.

Rendering pipeline
──────────────────
  Init → _prerender_all() builds one numpy (64×128) canvas per expression
         variant (base + blink + each speaking-mouth phase).

  Frame → copy pre-rendered canvas into working buffer self._buf,
          optionally overlay dynamic elements (dots, Zs),
          apply vertical float-offset via a single numpy slice,
          push the result to display.canvas and call display.show().

Why it's fast
─────────────
  • All geometry drawing uses numpy row-slice assignments instead of
    pixel-by-pixel Python loops  → drawing time < 0.5 ms per frame.
  • Pre-rendered canvases mean static expressions cost one memcpy.
  • Float is a numpy slice shift  → essentially free.
  • Bottleneck is now the I2C transfer (~23 ms at 400 kHz), not Python.
"""

import logging
import math
import random
import time
import threading
from enum import Enum
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── display geometry ─────────────────────────────────────────────
W, H = 128, 64

L_EYE   = (32, 21)
R_EYE   = (96, 21)
EYE_RX  = 11
EYE_RY  = 13
PUPIL_R = 5
MOUTH_X = 64
MOUTH_Y = 44

FLOAT_AMP  = 2      # ± pixels
FLOAT_FREQ = 1.2    # rad / s


class Expression(Enum):
    HAPPY     = "happy"
    SAD       = "sad"
    CONFUSED  = "confused"
    EXCITED   = "excited"
    NEUTRAL   = "neutral"
    THINKING  = "thinking"
    LISTENING = "listening"
    SLEEPING  = "sleeping"
    SPEAKING  = "speaking"
    RECORDING = "recording"


# Speaking mouth phases (pre-rendered at init)
_SPEAK_PHASES = ("small_smile", "open", "wide", "open", "small_smile", "open")


class ExpressionEngine:
    """Manages Fresh Buddy facial expressions and alive animations."""

    def __init__(self, display):
        self.display = display
        self.current = Expression.NEUTRAL

        self._stop   = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Working canvas — all drawing methods write here
        self._buf = np.zeros((H, W), dtype=np.uint8)

        # Pre-rendered canvases
        self._base:  Dict[Expression, np.ndarray] = {}
        self._blink: Dict[Expression, np.ndarray] = {}
        self._speak_mouths: Dict[str, np.ndarray] = {}

        self._prerender_all()

    # ── public API ───────────────────────────────────────────────

    def show_expression(self, name: str):
        try:
            expr = Expression(name.lower())
        except ValueError:
            logger.warning("Unknown expression: %s", name)
            expr = Expression.NEUTRAL
        self._switch(expr)

    def animate_speaking(self, duration: float = 0.1):
        """One mouth open/close cycle (for short external utterances)."""
        np.copyto(self._buf, self._base[self.current])
        self._buf |= self._speak_mouths["open"]
        self._commit(self._get_fy())
        time.sleep(duration)
        np.copyto(self._buf, self._base[self.current])
        self._commit(self._get_fy())

    def test_all(self):
        for expr in Expression:
            logger.info("Testing: %s", expr.value)
            self._switch(expr)
            time.sleep(2.0)
        self._switch(Expression.NEUTRAL)

    # ── float helper ─────────────────────────────────────────────

    def _get_fy(self) -> int:
        return int(FLOAT_AMP * math.sin(time.time() * FLOAT_FREQ))

    # ── commit: shift + push to display ─────────────────────────

    def _commit(self, fy: int = 0):
        """Apply vertical float offset to self._buf and push to display."""
        dc = self.display.canvas
        if dc is not None:
            if fy == 0:
                np.copyto(dc, self._buf)
            elif fy > 0:
                dc[:] = 0
                dc[fy:, :] = self._buf[:-fy, :]
            else:
                dc[:] = 0
                dc[:fy, :] = self._buf[-fy:, :]
        self.display.show()

    # ── switching & transition ────────────────────────────────────

    def _switch(self, expr: Expression):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._stop.clear()

        # Blink transition: close eyes for 70 ms, then open on new expression
        np.copyto(self._buf, self._blink[self.current])
        self._commit(0)
        time.sleep(0.07)

        self.current = expr
        np.copyto(self._buf, self._base[expr])
        self._commit(self._get_fy())

        loops = {
            Expression.SLEEPING: self._loop_sleeping,
            Expression.SPEAKING: self._loop_speaking,
            Expression.THINKING: self._loop_thinking,
        }
        fn = loops.get(expr, lambda: self._loop_blink(expr))
        self._thread = threading.Thread(target=fn, daemon=True)
        self._thread.start()

    # ── pre-rendering ─────────────────────────────────────────────

    def _prerender_all(self):
        """Render all expression variants once at startup."""
        for expr in Expression:
            # Base frame
            self._buf[:] = 0
            self._draw_eyes(expr)
            self._draw_mouth(expr)
            self._base[expr] = self._buf.copy()

            # Blink frame (closed eyes, same mouth)
            self._buf[:] = 0
            self._eye_blink(*L_EYE)
            self._eye_blink(*R_EYE)
            self._draw_mouth(expr)
            self._blink[expr] = self._buf.copy()

        # Speaking mouth phases (drawn on blank canvas — OR'd with eyes at runtime)
        for phase in set(_SPEAK_PHASES):
            self._buf[:] = 0
            self._draw_mouth_kind(MOUTH_X, MOUTH_Y, phase)
            self._speak_mouths[phase] = self._buf.copy()

        self._buf[:] = 0
        logger.debug("ExpressionEngine: pre-rendering complete")

    # ── eye drawing ──────────────────────────────────────────────

    def _draw_eyes(self, expr: Expression):
        for idx, (cx, cy) in enumerate((L_EYE, R_EYE)):
            if   expr == Expression.HAPPY:     self._eye_happy(cx, cy)
            elif expr == Expression.SAD:       self._eye_sad(cx, cy, left=(idx == 0))
            elif expr == Expression.EXCITED:   self._eye_big(cx, cy)
            elif expr == Expression.SLEEPING:  self._eye_sleeping(cx, cy)
            elif expr == Expression.CONFUSED:
                if idx == 0:
                    self._eye_normal(cx, cy)
                    self._brow(cx, cy, tilt=True)
                else:
                    self._eye_squint(cx, cy)
                    self._brow(cx, cy, raised=True)
            elif expr == Expression.THINKING:  self._eye_look_side(cx, cy, shift=+4)
            elif expr == Expression.RECORDING: self._eye_wide(cx, cy)
            else:                              self._eye_normal(cx, cy)

    # ── numpy-accelerated eye primitives ─────────────────────────

    def _fill_ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int = 1):
        """Fill ellipse using numpy row-slice assignments — O(ry) iterations."""
        for dy in range(-ry, ry + 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry) ** 2)))
            x0, x1 = max(0, cx - w), min(W, cx + w + 1)
            self._buf[y, x0:x1] = color

    def _eye_normal(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY)
        self._fill_ellipse(cx, cy, PUPIL_R, PUPIL_R, 0)
        if 0 <= cx - 3 < W and 0 <= cy - 5 < H:
            self._buf[cy - 5, cx - 3] = 1

    def _eye_big(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX + 2, EYE_RY + 2)
        self._fill_ellipse(cx, cy, PUPIL_R + 1, PUPIL_R + 1, 0)
        if 0 <= cx - 3 < W and 0 <= cy - 6 < H:
            self._buf[cy - 6, cx - 3] = 1

    def _eye_wide(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY + 3)
        self._fill_ellipse(cx, cy - 1, PUPIL_R - 1, PUPIL_R - 1, 0)
        if 0 <= cx - 3 < W and 0 <= cy - 6 < H:
            self._buf[cy - 6, cx - 3] = 1

    def _eye_happy(self, cx: int, cy: int):
        """Upper half of filled ellipse — happy ∩ arch."""
        for dy in range(-EYE_RY, 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(EYE_RX * math.sqrt(max(0.0, 1.0 - (dy / EYE_RY) ** 2)))
            x0, x1 = max(0, cx - w), min(W, cx + w + 1)
            self._buf[y, x0:x1] = 1

    def _eye_sad(self, cx: int, cy: int, left: bool = False):
        self._fill_ellipse(cx, cy + 2, EYE_RX - 1, EYE_RY - 2)
        self._fill_ellipse(cx, cy + 2, PUPIL_R - 1, PUPIL_R - 1, 0)
        # Sad brow: inner corner raised, outer corner lowered — mirrored per eye
        if left:
            self._line(cx - 5, cy - 6, cx + 3, cy - 9)  # outer-low → inner-high
        else:
            self._line(cx - 5, cy - 9, cx + 3, cy - 6)  # inner-high → outer-low

    def _eye_look_side(self, cx: int, cy: int, shift: int = 0):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY)
        self._fill_ellipse(cx + shift, cy, PUPIL_R, PUPIL_R, 0)
        px = cx + shift - 2
        if 0 <= px < W and 0 <= cy - 4 < H:
            self._buf[cy - 4, px] = 1

    def _eye_blink(self, cx: int, cy: int):
        """Three-pixel-tall closed band."""
        for dy in range(-1, 2):
            y = cy + dy
            if 0 <= y < H:
                x0 = max(0, cx - EYE_RX + 2)
                x1 = min(W, cx + EYE_RX - 1)
                self._buf[y, x0:x1] = 1

    def _eye_sleeping(self, cx: int, cy: int):
        """Parabolic U-arc — fully vectorized."""
        xs = np.arange(max(0, cx - EYE_RX), min(W, cx + EYE_RX + 1))
        ts = (xs - cx) / EYE_RX
        ys = (cy + (EYE_RY // 2) * ts ** 2).astype(int)
        mask = (ys >= 0) & (ys < H - 1)
        self._buf[ys[mask],     xs[mask]] = 1
        self._buf[ys[mask] + 1, xs[mask]] = 1

    def _eye_squint(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy + 3, EYE_RX - 2, EYE_RY // 2)
        self._fill_ellipse(cx, cy + 3, PUPIL_R - 2, PUPIL_R - 2, 0)

    def _brow(self, cx: int, cy: int, tilt: bool = False, raised: bool = False):
        by = cy - EYE_RY - 3
        if tilt:
            self._line(cx - 7, by, cx + 3, by + 4)
        elif raised:
            self._line(cx - 5, by - 4, cx + 5, by - 3)

    # ── mouth drawing ────────────────────────────────────────────

    _MOUTH_MAP = {
        Expression.HAPPY:     "big_smile",
        Expression.SAD:       "frown",
        Expression.EXCITED:   "open_happy",
        Expression.CONFUSED:  "wavy",
        Expression.THINKING:  "small_smile",
        Expression.RECORDING: "flat",
        Expression.LISTENING: "oval",
        Expression.SLEEPING:  "tiny",
        Expression.SPEAKING:  "small_smile",
        Expression.NEUTRAL:   "smile",
    }

    def _draw_mouth(self, expr: Expression, override: str = None):
        self._draw_mouth_kind(MOUTH_X, MOUTH_Y, override or self._MOUTH_MAP.get(expr, "smile"))

    def _draw_mouth_kind(self, cx: int, y: int, kind: str):
        if   kind == "smile":       self._m_smile(cx, y, w=12, h=6, thick=2)
        elif kind == "big_smile":   self._m_smile(cx, y, w=16, h=8, thick=2)
        elif kind == "small_smile": self._m_smile(cx, y, w=8,  h=3, thick=1)
        elif kind == "frown":       self._m_frown(cx, y)
        elif kind in ("open_happy", "wide"): self._m_open_happy(cx, y)
        elif kind == "open":        self._m_open(cx, y)
        elif kind == "wavy":        self._m_wavy(cx, y)
        elif kind == "flat":
            self._hline(cx - 8, y,     cx + 8)
            self._hline(cx - 8, y + 1, cx + 8)
        elif kind == "oval":
            self._fill_ellipse(cx, y + 4, 7, 5)
            self._fill_ellipse(cx, y + 4, 4, 3, 0)
        elif kind == "tiny":
            self._hline(cx - 4, y, cx + 4)

    def _m_smile(self, cx: int, y: int, w: int, h: int, thick: int):
        # Vertex at bottom (y+h), arms rise toward the edges → smile shape ∪
        xs = np.arange(-w, w + 1)
        ys = (y + h - h * (xs / w) ** 2).astype(int)
        for t in range(thick):
            ys_t = ys + t
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys_t >= 0) & (ys_t < H)
            self._buf[ys_t[mask], (xs + cx)[mask]] = 1

    def _m_frown(self, cx: int, y: int):
        # Vertex at top (y), arms drop toward the edges → frown shape ∩
        xs = np.arange(-12, 13)
        ys = (y + 6 * (xs / 12) ** 2).astype(int)
        for dy in range(2):
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys + dy >= 0) & (ys + dy < H)
            self._buf[(ys + dy)[mask], (xs + cx)[mask]] = 1

    def _m_open_happy(self, cx: int, y: int):
        self._fill_ellipse(cx, y + 8, 15, 9)
        self._fill_ellipse(cx, y + 9, 11, 6, 0)
        # Teeth stripe — redraw on top of inner black
        x0, x1 = max(0, cx - 9), min(W, cx + 10)
        for dy in range(3):
            row = y + 3 + dy
            if 0 <= row < H:
                self._buf[row, x0:x1] = 1
        self._fill_ellipse(cx, y + 14, 7, 3)   # tongue

    def _m_open(self, cx: int, y: int):
        self._fill_ellipse(cx, y + 5, 9, 6)
        self._fill_ellipse(cx, y + 5, 6, 3, 0)

    def _m_wavy(self, cx: int, y: int):
        xs = np.arange(-10, 11)
        ys = (y + 2 * np.sin(xs * math.pi / 5)).astype(int)
        for dy in range(2):
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys + dy >= 0) & (ys + dy < H)
            self._buf[(ys + dy)[mask], (xs + cx)[mask]] = 1

    # ── vectorized geometry helpers ───────────────────────────────

    def _line(self, x1: int, y1: int, x2: int, y2: int):
        """Vectorized Bresenham via linspace."""
        n = max(abs(x2 - x1), abs(y2 - y1)) + 1
        xs = np.round(np.linspace(x1, x2, n)).astype(int)
        ys = np.round(np.linspace(y1, y2, n)).astype(int)
        mask = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        self._buf[ys[mask], xs[mask]] = 1

    def _hline(self, x0: int, y: int, x1: int):
        if 0 <= y < H:
            self._buf[y, max(0, min(x0, x1)):min(W, max(x0, x1) + 1)] = 1

    # ── sleeping Z helper (drawn on self._buf, no display.draw_text) ──

    def _z_big(self, x: int, y: int):
        self._hline(x, y,     x + 4)
        self._line( x + 4, y, x,     y + 6)
        self._hline(x, y + 6, x + 4)

    def _z_small(self, x: int, y: int):
        self._hline(x, y,     x + 3)
        self._line( x + 3, y, x,     y + 4)
        self._hline(x, y + 4, x + 3)

    # ── animation loops ──────────────────────────────────────────

    def _loop_blink(self, expr: Expression):
        """Blink every 1.5–3.5 s; 25 % chance of double-blink."""
        while not self._stop.wait(random.uniform(1.5, 3.5)):
            # Blink frame from pre-rendered canvas
            np.copyto(self._buf, self._blink[expr])
            self._commit(0)

            if self._stop.wait(0.10):
                break

            np.copyto(self._buf, self._base[expr])
            self._commit(self._get_fy())

            if random.random() < 0.25:
                if self._stop.wait(0.12):
                    break
                np.copyto(self._buf, self._blink[expr])
                self._commit(0)
                if self._stop.wait(0.10):
                    break
                np.copyto(self._buf, self._base[expr])
                self._commit(self._get_fy())

    def _loop_sleeping(self):
        """Float face + animated Z letters."""
        z_off = 0.0
        # Pre-rendered sleeping base (eyes only — mouth added in prerender)
        sleep_base = self._base[Expression.SLEEPING]
        while not self._stop.is_set():
            fy = self._get_fy()
            np.copyto(self._buf, sleep_base)
            # Floating Zs — drawn directly on self._buf
            z_data = ((82,  12, False), (94, 18, True), (104, 24, True))
            for zx, zy_base, small in z_data:
                zy = int(zy_base - z_off) + fy
                if 2 <= zy < H - 8:
                    if small:
                        self._z_small(zx, zy)
                    else:
                        self._z_big(zx, zy)
            self._commit(fy)
            z_off = (z_off + 1.8) % 22
            if self._stop.wait(0.55):
                break

    def _loop_speaking(self):
        """Cycle pre-rendered mouth phases over pre-rendered eyes."""
        # Eyes-only canvas for speaking: base frame but clear mouth area
        speak_eyes = self._base[Expression.SPEAKING].copy()
        speak_eyes[MOUTH_Y - 2:, :] = 0  # wipe mouth region from base

        i = 0
        while not self._stop.wait(0.09):   # ~11 FPS mouth animation
            fy = self._get_fy()
            phase = _SPEAK_PHASES[i % len(_SPEAK_PHASES)]
            # Compose: eyes OR mouth (no overlap since eye/mouth areas don't overlap)
            np.copyto(self._buf, speak_eyes)
            self._buf |= self._speak_mouths[phase]
            self._commit(fy)
            i += 1

    def _loop_thinking(self):
        """Animated ellipsis dots over pre-rendered thinking face."""
        think_base = self._base[Expression.THINKING]
        # Dot positions (to the right of the mouth, in empty space)
        dot_xs = [MOUTH_X + 22 + d * 8 for d in range(3)]
        dot_y  = 41
        dot = 0
        while not self._stop.wait(0.33):
            fy = self._get_fy()
            np.copyto(self._buf, think_base)
            for d in range(dot + 1):
                self._fill_ellipse(dot_xs[d], dot_y, 2, 2)
            self._commit(fy)
            dot = (dot + 1) % 3
