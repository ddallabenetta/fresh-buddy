"""Expression Engine for Fresh Buddy — 800×480 High-Res Edition.

Rendering pipeline
─────────────────
  Init → _prerender_all() builds numpy (480×800) canvases per expression
         variant (base + blink + speaking phases).

  Frame → copy pre-rendered canvas, overlay dynamic effects (sparkles, Zs,
           tears), apply vertical float + scanlines, push to display.

80s Futuristic Enhancements
───────────────────────────
  • Matrix green (#39FF14) / cyan / magenta / amber palette
  • Smooth 300ms ease-out-expo transitions between expressions
  • Per-expression animated effects (starbursts, tears, Zs, sparkles)
  • Scanline overlay scrolling slowly for CRT feel
  • Glow/bloom via multi-pass dilation
  • CRT corner-darkening for screen-curvature hint
  • 30fps animation controller with frame throttling
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

# ══════════════════════════════════════════════════════════════════
# DISPLAY GEOMETRY — 800×480
# ══════════════════════════════════════════════════════════════════
W, H = 800, 480

# Scale factor from original 128×64 design
# x: 800/128 ≈ 6.25   y: 480/64 = 7.5
SX, SY = 6.25, 7.5

# Body (BMO-style rounded rectangle)
BODY_X, BODY_Y = 125, 60      # top-left of body bounding box
BODY_W, BODY_H = 550, 360    # body dimensions
BODY_RX, BODY_RY = 55, 50     # corner radius

# Face inset within body
FACE_X  = BODY_X + 30
FACE_Y  = BODY_Y + 30
FACE_W  = BODY_W - 60         # = 490
FACE_H  = BODY_H - 60         # = 270

# Eyes — scaled from original (32,21)/(96,21) at 128×64
L_EYE   = (265, 148)          # ~32*6.25, 21*7.5
R_EYE   = (555, 148)
EYE_RX  = int(11 * SX)        # ≈ 69
EYE_RY  = int(13 * SY)        # ≈ 98
PUPIL_R = int(5  * SX)        # ≈ 31
GLINT_R = max(3, int(3 * SX)) # ≈ 19

# Mouth
MOUTH_X = 410
MOUTH_Y = 280

# Breathing / float
FLOAT_AMP  = 6
FLOAT_FREQ = 1.0

# ══════════════════════════════════════════════════════════════════
# COLOUR PALETTE (8-bit grayscale for local display)
# ══════════════════════════════════════════════════════════════════
# The display uses 8-bit grayscale; 255 = brightest
G   = 255      # Matrix green — primary
C   = 200      # Cyan accent
M   = 180      # Magenta accent
A   = 210      # Amber / warning
BL  = 0        # Black / background


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


# Speaking mouth phases
_SPEAK_PHASES = ("small_smile", "open", "wide", "open", "small_smile", "open")


# ══════════════════════════════════════════════════════════════════
# EASING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1.0 else 1.0 - math.pow(2, -10 * t)

def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    return 1.0 - math.pow(-2 * t + 2, 2) / 2

def ease_out_bounce(t: float) -> float:
    n1 = 7.5625
    d = 1.0
    if t < 0.75 / d:
        return n1 * math.pow(t / 0.75, 2)
    elif t < 0.9 / d:
        t_adj = t - 0.825 / d
        return n1 * math.pow(t_adj / 0.075, 2) + 0.85
    else:
        t_adj = t - 0.95 / d
        return n1 * math.pow(t_adj / 0.05, 2) + 0.9

def ease_out_elastic(t: float) -> float:
    if t == 0.0 or t == 1.0:
        return t
    p = 0.35
    return math.pow(2, -10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1.0


# ══════════════════════════════════════════════════════════════════
# ANIMATION CONTROLLER
# ══════════════════════════════════════════════════════════════════

class AnimationController:
    """Frame timing, scanlines, transition blending."""

    TARGET_FPS = 30
    _FRAME_MS  = 1000.0 / TARGET_FPS

    def __init__(self):
        self._last_frame_time = 0.0
        self._transition_start = 0.0
        self._transition_duration = 300.0
        self._from_expr: Optional[Expression] = None
        self._to_expr: Optional[Expression] = None
        self._blend_factor = 0.0
        self._scanline_off = 0.0
        self._frame_count = 0

    # ── transition ─────────────────────────────────────────────

    def begin_transition(self, from_expr: Expression, to_expr: Expression,
                         duration_ms: float = 300.0):
        self._from_expr = from_expr
        self._to_expr = to_expr
        self._blend_factor = 0.0
        self._transition_start = time.time() * 1000.0
        self._transition_duration = duration_ms

    def update_transition(self) -> float:
        if self._to_expr is None:
            return 1.0
        elapsed = (time.time() * 1000.0) - self._transition_start
        raw = min(1.0, elapsed / self._transition_duration)
        self._blend_factor = ease_out_expo(raw)
        return self._blend_factor

    def is_transitioning(self) -> bool:
        return self._from_expr is not None and self._blend_factor < 1.0

    def finalize_transition(self):
        self._from_expr = None
        self._to_expr = None
        self._blend_factor = 0.0

    # ── frame throttle ──────────────────────────────────────────

    def frame_throttle(self) -> bool:
        now = time.time() * 1000.0
        elapsed = now - self._last_frame_time
        if elapsed < self._FRAME_MS:
            return False
        self._last_frame_time = now - (elapsed - self._FRAME_MS)
        self._frame_count += 1
        return True

    # ── scanlines ───────────────────────────────────────────────

    def advance_scanlines(self, dt_ms: float):
        # One full cycle over 8 seconds
        self._scanline_off = (self._scanline_off + dt_ms / 8000.0 * H) % H

    def apply_scanlines(self, canvas: np.ndarray):
        """Overlay CRT scanlines: darken every 3rd row, scrolling slowly."""
        off = int(self._scanline_off) % 3
        canvas[off::3, :] = (canvas[off::3, :] * 0.65).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════
# EXPRESSION ENGINE
# ══════════════════════════════════════════════════════════════════

class ExpressionEngine:
    """Manages Fresh Buddy facial expressions and alive animations."""

    def __init__(self, display):
        self.display = display
        self.current = Expression.NEUTRAL
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Working canvas — all drawing writes here
        self._buf = np.full((H, W), BL, dtype=np.uint8)

        # Pre-rendered canvases
        self._base:  Dict[Expression, np.ndarray] = {}
        self._blink: Dict[Expression, np.ndarray] = {}
        self._speak_mouths: Dict[str, np.ndarray] = {}

        # Animation controller
        self._anim = AnimationController()

        self._prerender_all()

    # ── public API (backward-compatible) ───────────────────────

    @property
    def current_expression(self) -> Expression:
        return self.current

    def show_expression(self, name: str):
        try:
            expr = Expression(name.lower())
        except ValueError:
            logger.warning("Unknown expression: %s", name)
            expr = Expression.NEUTRAL
        self._switch(expr)

    def animate_speaking(self, duration: float = 0.1):
        np.copyto(self._buf, self._base[self.current])
        self._buf |= self._speak_mouths["open"]
        self._overlay_effects()
        self._commit(self._get_fy())
        time.sleep(duration)
        np.copyto(self._buf, self._base[self.current])
        self._overlay_effects()
        self._commit(self._get_fy())

    def test_all(self):
        for expr in Expression:
            logger.info("Testing: %s", expr.value)
            self._switch(expr)
            time.sleep(2.0)
        self._switch(Expression.NEUTRAL)

    # ── float helper ───────────────────────────────────────────

    def _get_fy(self) -> int:
        return int(FLOAT_AMP * math.sin(time.time() * FLOAT_FREQ))

    # ── commit ─────────────────────────────────────────────────

    def _commit(self, fy: int = 0):
        dc = self.display.canvas
        if dc is not None:
            if fy == 0:
                np.copyto(dc, self._buf)
            elif fy > 0:
                dc[:] = BL
                dc[fy:, :] = self._buf[:-fy, :]
            else:
                dc[:] = BL
                dc[:fy, :] = self._buf[-fy:, :]
        self.display.show()

    # ── effects overlay ────────────────────────────────────────

    def _overlay_effects(self):
        expr = self.current
        t = time.time()

        if   expr == Expression.HAPPY:     self._effect_happy_sparkles(t)
        elif expr == Expression.EXCITED:   self._effect_excited_starburst(t)
        elif expr == Expression.SAD:      self._effect_sad_tears(t)
        elif expr == Expression.LISTENING: self._effect_listening_soundwaves(t)
        elif expr == Expression.RECORDING: self._effect_recording_indicator(t)
        elif expr == Expression.CONFUSED: self._effect_confused_wobble(t)
        elif expr == Expression.THINKING: self._effect_thinking_processing(t)

        # Always apply CRT corners
        self._apply_crt_corners()

    # ── per-expression effects ─────────────────────────────────

    def _effect_happy_sparkles(self, t: float):
        """Sparkle dots orbiting eyes (8 per eye)."""
        for (cx, cy), phase in [(L_EYE, 0.0), (R_EYE, math.pi)]:
            for k in range(8):
                angle = t * 2.0 + phase + k * (math.pi / 4)
                r = int(EYE_RX * 0.85)
                sx = int(cx + r * math.cos(angle))
                sy = int(cy - EYE_RY * 0.3 + r * 0.5 * math.sin(angle))
                sr = max(2, GLINT_R // 4)
                self._fill_ellipse(sx, sy, sr, sr, G)
                # Tiny cross sparkle
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    if 0 <= sx+dx < W and 0 <= sy+dy < H:
                        self._buf[sy+dy, sx+dx] = G

    def _effect_excited_starburst(self, t: float):
        """8-point starburst rays around each eye."""
        for cx, cy in (L_EYE, R_EYE):
            base_r = int(EYE_RX * 1.4)
            for ray in range(8):
                angle = ray * (math.pi / 4) + t * 3.0
                pulse = 1.0 + 0.3 * math.sin(t * 7.0 + ray * 0.8)
                r = int(base_r * pulse)
                x1 = int(cx + r * math.cos(angle))
                y1 = int(cy + r * math.sin(angle))
                self._thick_line(cx, cy, x1, y1, color=G)
            # Centre glint
            self._fill_ellipse(cx, cy, max(3, PUPIL_R//3), max(3, PUPIL_R//3), G)

    def _effect_sad_tears(self, t: float):
        """Tear streaks falling from sad eyes."""
        for cx, cy in (L_EYE, R_EYE):
            tx = cx + int(4 * math.sin(t * 0.7))
            base_y = cy + EYE_RY - 5
            length = int(30 + 20 * math.sin(t * 1.2))
            for dy in range(0, length, 2):
                row = base_y + dy
                if 0 <= row < H and 0 <= tx < W:
                    self._buf[row, tx] = G
                if 0 <= row < H and 0 <= tx - 2 < W:
                    self._buf[row, tx - 2] = G
                if 0 <= row < H and 0 <= tx + 2 < W:
                    self._buf[row, tx + 2] = G

    def _effect_listening_soundwaves(self, t: float):
        """Sound-wave arcs from mouth area."""
        for ring in range(3):
            base_r = 40 + ring * 35
            r = base_r + int(12 * math.sin(t * 4.0 + ring * 1.2))
            for dx in range(-80, 81, 2):
                x = MOUTH_X + dx
                y_off_sq = max(0, r * r - dx * dx)
                y_off = int(math.sqrt(y_off_sq) * 0.35)
                for sign in (-1, 1):
                    y = MOUTH_Y - 10 + sign * y_off
                    if 0 <= y < H and 0 <= x < W:
                        self._buf[y, x] = G

    def _effect_recording_indicator(self, t: float):
        """Pulsing red dot + vibration in top-left corner."""
        pulse = 0.5 + 0.5 * math.sin(t * 6.0)
        dot_r = int(8 + pulse * 6)
        vib_x = int(4 * math.sin(t * 22.0))
        vib_y = int(3 * math.cos(t * 18.0))
        cx, cy = 45 + vib_x, 40 + vib_y
        self._fill_ellipse(cx, cy, dot_r, dot_r, A)
        # REC text dots (tiny 3×5 bitmap)
        if int(t * 3.0) % 2 == 0:
            letters = {"R": [[1,0,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
                       "E": [[1,1,1],[1,0,0],[1,1,1],[1,0,0],[1,1,1]],
                       "C": [[1,1,1],[1,0,0],[1,0,0],[1,0,0],[1,1,1]]}
            for li, ch in enumerate("REC"):
                for py in range(5):
                    for px in range(3):
                        if letters[ch][py][px]:
                            x, y = 75 + li * 14 + px * 2, 30 + py * 2
                            if 0 <= y < H and 0 <= x < W:
                                self._buf[y, x] = A

    def _effect_confused_wobble(self, t: float):
        """Wobbling question mark."""
        wobble = 0.5 * math.sin(t * 5.0)
        qx, qy_base = 690, 120
        for deg in range(-40, 220, 8):
            rad = math.radians(deg + wobble * 25)
            qx_i = int(qx + 18 * math.cos(rad))
            qy_i = int(qy_base + 18 * math.sin(rad))
            if 0 <= qx_i < W and 0 <= qy_i < H:
                self._buf[qy_i, qx_i] = G
        dot_y = int(qy_base + 28 + wobble * 3)
        if 0 <= dot_y < H:
            self._buf[dot_y, qx - 3:qx + 5] = G

    def _effect_thinking_processing(self, t: float):
        """PROCESSING text flicker on right side."""
        if int(t * 5.0) % 4 == 0:
            # Mini "PROC" text via dots
            px, py_base = 640, 235
            rows = [[1,1,1,0,1,1,1,0,1,0,1,0,1,1],
                    [1,0,0,0,1,0,0,0,1,0,1,0,0,1],
                    [1,1,1,0,1,1,1,0,1,0,1,0,0,1],
                    [0,0,0,0,1,0,0,0,1,0,1,0,0,1],
                    [1,1,1,0,1,0,0,0,1,1,1,0,0,1]]
            for py, row in enumerate(rows):
                for px_i, bit in enumerate(row):
                    if bit and 0 <= px + px_i < W and 0 <= py_base + py < H:
                        self._buf[py_base + py, px + px_i] = G

    def _apply_crt_corners(self):
        """Darken corners for CRT screen-curvature hint."""
        r = 40
        for y in range(r + 1):
            for x in range(r + 1):
                d = math.sqrt((r - x)**2 + (r - y)**2)
                if d > r:
                    alpha = min(1.0, (d - r) / 20)
                    if alpha > 0.65:
                        for cy_c, cx_c in [(y, x), (y, W-1-x),
                                            (H-1-y, x), (H-1-y, W-1-x)]:
                            if 0 <= cy_c < H and 0 <= cx_c < W:
                                self._buf[cy_c, cx_c] = BL

    # ── glow / bloom ───────────────────────────────────────────

    def _apply_glow(self, color: int = G):
        """Bloom effect: dilate and OR back for glow halo."""
        dilated = self._dilate(self._buf, color)
        self._buf = np.clip(self._buf.astype(np.int16) + (dilated > 0).astype(np.int16) * color // 2,
                            0, 255).astype(np.uint8)

    def _dilate(self, arr: np.ndarray, color: int) -> np.ndarray:
        """Dilate lit pixels by 2px radius."""
        out = arr.copy()
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dy == 0 and dx == 0:
                    continue
                yy, xx = dy, dx
                out[max(0,yy):min(H,H+yy), max(0,xx):min(W,W+xx)] |= arr[max(0,-yy):min(H,H-yy), max(0,-xx):min(W,W-xx)]
        return out

    # ── switching & transition ──────────────────────────────────

    def _switch(self, expr: Expression):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._stop.clear()

        prev = self.current
        self._anim.begin_transition(prev, expr, duration_ms=300.0)

        # Immediately commit target frame (API responsiveness)
        self.current = expr
        np.copyto(self._buf, self._base[expr])
        self._overlay_effects()
        self._commit(self._get_fy())

        self._thread = threading.Thread(target=self._run_transition,
                                        args=(prev, expr), daemon=True)
        self._thread.start()

    def _run_transition(self, from_expr: Expression, to_expr: Expression):
        # Blink-out (70ms)
        np.copyto(self._buf, self._blink[from_expr])
        self._commit(0)
        if self._stop.wait(0.07):
            return

        # Blend-in (300ms)
        from_base = self._base[from_expr]
        to_base   = self._base[to_expr]
        blend_start = time.time()
        duration = 0.30

        while not self._stop.is_set():
            elapsed = time.time() - blend_start
            t_raw = min(1.0, elapsed / duration)
            t_eased = ease_out_expo(t_raw)

            blended = (from_base.astype(np.float32) * (1.0 - t_eased) +
                       to_base.astype(np.float32) * t_eased)
            np.copyto(self._buf, blended.astype(np.uint8))
            self._overlay_effects()
            self._commit(self._get_fy())

            if t_raw >= 1.0:
                break
            time.sleep(self._anim._FRAME_MS / 1000.0)

        self._anim.finalize_transition()

        # Start expression-specific loop
        loops = {
            Expression.SLEEPING:  self._loop_sleeping,
            Expression.SPEAKING:  self._loop_speaking,
            Expression.THINKING:  self._loop_thinking,
            Expression.EXCITED:   self._loop_excited,
            Expression.HAPPY:     self._loop_happy,
            Expression.RECORDING: self._loop_recording,
            Expression.LISTENING: self._loop_listening,
        }
        fn = loops.get(to_expr, lambda: self._loop_blink(to_expr))
        self._thread = threading.Thread(target=fn, daemon=True)
        self._thread.start()

    # ── pre-rendering ──────────────────────────────────────────

    def _prerender_all(self):
        for expr in Expression:
            # Base frame
            self._buf[:] = BL
            self._draw_body()
            self._draw_face_outline()
            self._draw_eyes(expr)
            self._draw_mouth(expr)
            self._base[expr] = self._buf.copy()

            # Blink frame
            self._buf[:] = BL
            self._draw_body()
            self._draw_face_outline()
            self._eye_blink(*L_EYE)
            self._eye_blink(*R_EYE)
            self._draw_mouth(expr)
            self._blink[expr] = self._buf.copy()

        # Speaking mouth phases
        for phase in set(_SPEAK_PHASES):
            self._buf[:] = BL
            self._draw_mouth_kind(MOUTH_X, MOUTH_Y, phase)
            self._speak_mouths[phase] = self._buf.copy()

        self._buf[:] = BL
        logger.debug("ExpressionEngine 800×480: pre-rendering complete")

    # ── body drawing ───────────────────────────────────────────

    def _draw_body(self):
        """BMO-style rounded rectangle body."""
        self._fill_rounded_rect(BODY_X, BODY_Y, BODY_W, BODY_H,
                                BODY_RX, BODY_RY, G)

    def _draw_face_outline(self):
        """Face inset oval outline."""
        # Clear interior
        self._fill_rounded_rect(FACE_X, FACE_Y, FACE_W, FACE_H,
                                BODY_RX - 10, BODY_RY - 10, BL, fill=True)
        # Draw outline
        self._fill_rounded_rect(FACE_X, FACE_Y, FACE_W, FACE_H,
                                BODY_RX - 10, BODY_RY - 10, G, fill=False)

    def _fill_rounded_rect(self, x: int, y: int, w: int, h: int,
                           rx: int, ry: int, color: int, fill: bool = True):
        """Draw rounded rectangle using numpy slices."""
        if fill:
            # Main rectangle fill
            self._buf[y:y+h, x:x+w] = color
            # Clear corners
            for cy_off, cx_off in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                for dy in range(-ry, ry + 1):
                    cy = y + ry + dy * cy_off
                    if not (y <= cy < y + h):
                        continue
                    rw = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry)**2)))
                    if cx_off == -1:
                        self._buf[cy, x:x + rw] = BL
                    else:
                        self._buf[cy, x + w - rw:x + w] = BL
        else:
            # Outline only
            for dy in range(-ry, ry + 1):
                cy = y + dy
                if not (y <= cy < y + h):
                    continue
                rw = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry)**2)))
                self._buf[cy, x:x + rw] = color
                self._buf[cy, x + w - rw:x + w] = color
            for dx in range(rx, w - rx):
                cx = x + dx
                if w - rx <= cx < w:
                    continue
                self._buf[y, x + rx:x + w - rx] = color
                self._buf[y + h - 1, x + rx:x + w - rx] = color

    # ── eye drawing ────────────────────────────────────────────

    def _draw_eyes(self, expr: Expression):
        for idx, (cx, cy) in enumerate((L_EYE, R_EYE)):
            if   expr == Expression.HAPPY:     self._eye_happy(cx, cy)
            elif expr == Expression.SAD:      self._eye_sad(cx, cy, left=(idx == 0))
            elif expr == Expression.EXCITED:  self._eye_big(cx, cy)
            elif expr == Expression.SLEEPING: self._eye_sleeping(cx, cy)
            elif expr == Expression.CONFUSED:
                if idx == 0:
                    self._eye_normal(cx, cy)
                    self._brow(cx, cy, tilt=True)
                else:
                    self._eye_squint(cx, cy)
                    self._brow(cx, cy, raised=True)
            elif expr == Expression.THINKING: self._eye_look_side(cx, cy, shift=+20)
            elif expr == Expression.RECORDING: self._eye_wide(cx, cy)
            elif expr == Expression.LISTENING: self._eye_attentive(cx, cy)
            else:                              self._eye_normal(cx, cy)

    def _fill_ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int = G):
        """Fill ellipse using numpy row-slice assignments."""
        for dy in range(-ry, ry + 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry) ** 2)))
            x0, x1 = max(0, cx - w), min(W, cx + w + 1)
            self._buf[y, x0:x1] = color

    def _eye_normal(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY, G)
        self._fill_ellipse(cx, cy, PUPIL_R, PUPIL_R, BL)
        # Glint
        if 0 <= cx - 10 < W and 0 <= cy - EYE_RY + 10 < H:
            self._fill_ellipse(cx - 10, cy - EYE_RY + 10, GLINT_R, GLINT_R, G)

    def _eye_big(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX + 15, EYE_RY + 15, G)
        self._fill_ellipse(cx, cy, PUPIL_R + 5, PUPIL_R + 5, BL)
        if 0 <= cx - 10 < W and 0 <= cy - EYE_RY + 10 < H:
            self._fill_ellipse(cx - 10, cy - EYE_RY + 10, GLINT_R, GLINT_R, G)

    def _eye_wide(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY + 20, G)
        self._fill_ellipse(cx, cy - 3, PUPIL_R, PUPIL_R, BL)

    def _eye_attentive(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy, EYE_RX + 5, EYE_RY + 3, G)
        self._fill_ellipse(cx, cy, PUPIL_R + 3, PUPIL_R + 3, BL)
        if 0 <= cx - 8 < W and 0 <= cy - EYE_RY + 8 < H:
            self._fill_ellipse(cx - 8, cy - EYE_RY + 8, GLINT_R - 3, GLINT_R - 3, G)

    def _eye_happy(self, cx: int, cy: int):
        """Upper arc — happy arch."""
        for dy in range(-EYE_RY, 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(EYE_RX * math.sqrt(max(0.0, 1.0 - (dy / EYE_RY)**2)))
            x0, x1 = max(0, cx - w), min(W, cx + w + 1)
            self._buf[y, x0:x1] = G

    def _eye_sad(self, cx: int, cy: int, left: bool = False):
        self._fill_ellipse(cx, cy + 8, EYE_RX - 10, EYE_RY - 15, G)
        self._fill_ellipse(cx, cy + 8, PUPIL_R - 5, PUPIL_R - 5, BL)
        if left:
            self._thick_line(cx - 30, cy - EYE_RY - 5, cx + 20, cy - EYE_RY - 25, G)
        else:
            self._thick_line(cx - 30, cy - EYE_RY - 25, cx + 20, cy - EYE_RY - 5, G)

    def _eye_look_side(self, cx: int, cy: int, shift: int = 0):
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY, G)
        self._fill_ellipse(cx + shift, cy, PUPIL_R, PUPIL_R, BL)
        px = cx + shift - 8
        if 0 <= px < W and 0 <= cy - EYE_RY + 10 < H:
            self._fill_ellipse(px, cy - EYE_RY + 10, GLINT_R - 3, GLINT_R - 3, G)

    def _eye_blink(self, cx: int, cy: int):
        """Horizontal band for blink."""
        for dy in range(-4, 5):
            y = cy + dy
            if 0 <= y < H:
                x0 = max(0, cx - EYE_RX + 8)
                x1 = min(W, cx + EYE_RX - 8)
                self._buf[y, x0:x1] = G

    def _eye_sleeping(self, cx: int, cy: int):
        """Parabolic U-arc for closed eyes."""
        xs = np.arange(max(0, cx - EYE_RX), min(W, cx + EYE_RX + 1))
        ts = (xs - cx) / EYE_RX
        ys = (cy + (EYE_RY // 2) * ts**2).astype(int)
        mask = (ys >= 0) & (ys < H)
        self._buf[ys[mask],     xs[mask]] = G
        self._buf[ys[mask] + 1, xs[mask]] = G

    def _eye_squint(self, cx: int, cy: int):
        self._fill_ellipse(cx, cy + 12, EYE_RX - 15, EYE_RY // 2, G)
        self._fill_ellipse(cx, cy + 12, PUPIL_R - 8, PUPIL_R - 8, BL)

    def _brow(self, cx: int, cy: int, tilt: bool = False, raised: bool = False):
        by = cy - EYE_RY - 15
        if tilt:
            self._thick_line(cx - 40, by,     cx + 25, by + 25, G)
        elif raised:
            self._thick_line(cx - 35, by - 20, cx + 35, by - 12, G)

    # ── mouth drawing ──────────────────────────────────────────

    _MOUTH_MAP = {
        Expression.HAPPY:     "big_smile",
        Expression.SAD:       "frown",
        Expression.EXCITED:   "open_happy",
        Expression.CONFUSED:  "wavy",
        Expression.THINKING:  "small_smile",
        Expression.RECORDING:  "flat",
        Expression.LISTENING: "oval",
        Expression.SLEEPING:  "tiny",
        Expression.SPEAKING:  "small_smile",
        Expression.NEUTRAL:   "smile",
    }

    def _draw_mouth(self, expr: Expression, override: str = None):
        self._draw_mouth_kind(MOUTH_X, MOUTH_Y,
                               override or self._MOUTH_MAP.get(expr, "smile"))

    def _draw_mouth_kind(self, cx: int, y: int, kind: str):
        if   kind == "smile":       self._m_smile(cx, y, w=75,  h=35, thick=6)
        elif kind == "big_smile":  self._m_smile(cx, y, w=100, h=50, thick=8)
        elif kind == "small_smile": self._m_smile(cx, y, w=50,  h=20, thick=4)
        elif kind == "frown":      self._m_frown(cx, y)
        elif kind in ("open_happy", "wide"): self._m_open_happy(cx, y)
        elif kind == "open":       self._m_open(cx, y)
        elif kind == "wavy":       self._m_wavy(cx, y)
        elif kind == "flat":
            self._hline(cx - 50, y,     cx + 50, G)
            self._hline(cx - 50, y + 4, cx + 50, G)
        elif kind == "oval":
            self._fill_ellipse(cx, y + 20, 45, 32, G)
            self._fill_ellipse(cx, y + 20, 28, 20, BL)
        elif kind == "tiny":
            self._hline(cx - 25, y, cx + 25, G)

    def _m_smile(self, cx: int, y: int, w: int, h: int, thick: int):
        xs = np.arange(-w, w + 1)
        ys = (y + h - h * (xs / w)**2).astype(int)
        for t in range(thick):
            ys_t = ys + t
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys_t >= 0) & (ys_t < H)
            self._buf[ys_t[mask], (xs + cx)[mask]] = G

    def _m_frown(self, cx: int, y: int):
        xs = np.arange(-75, 76)
        ys = (y + 35 * (xs / 75)**2).astype(int)
        for dy in range(4):
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys + dy >= 0) & (ys + dy < H)
            self._buf[(ys + dy)[mask], (xs + cx)[mask]] = G

    def _m_open_happy(self, cx: int, y: int):
        self._fill_ellipse(cx, y + 45, 95, 58, G)
        self._fill_ellipse(cx, y + 48, 70, 40, BL)
        # Teeth
        x0, x1 = max(0, cx - 58), min(W, cx + 59)
        for dy in range(18):
            row = y + 15 + dy
            if 0 <= row < H:
                self._buf[row, x0:x1] = G
        # Tongue
        self._fill_ellipse(cx, y + 80, 45, 18, G)

    def _m_open(self, cx: int, y: int):
        self._fill_ellipse(cx, y + 28, 58, 38, G)
        self._fill_ellipse(cx, y + 28, 38, 22, BL)

    def _m_wavy(self, cx: int, y: int):
        xs = np.arange(-65, 66)
        ys = (y + 12 * np.sin(xs * math.pi / 32)).astype(int)
        for dy in range(4):
            mask = (xs + cx >= 0) & (xs + cx < W) & (ys + dy >= 0) & (ys + dy < H)
            self._buf[(ys + dy)[mask], (xs + cx)[mask]] = G

    # ── vectorized geometry ────────────────────────────────────

    def _thick_line(self, x1: int, y1: int, x2: int, y2: int, color: int = G, thick: int = 3):
        """Bresenham line with thickness."""
        for d in range(-thick//2, thick//2 + 1):
            self._line(x1, y1 + d, x2, y2 + d, color)
            self._line(x1 + d, y1, x2 + d, y2, color)

    def _line(self, x1: int, y1: int, x2: int, y2: int, color: int = G):
        n = max(abs(x2 - x1), abs(y2 - y1)) + 1
        xs = np.round(np.linspace(x1, x2, n)).astype(int)
        ys = np.round(np.linspace(y1, y2, n)).astype(int)
        mask = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        self._buf[ys[mask], xs[mask]] = color

    def _hline(self, x0: int, y: int, x1: int, color: int = G):
        if 0 <= y < H:
            self._buf[y, max(0, min(x0, x1)):min(W, max(x0, x1) + 1)] = color

    # ── sleeping Z ────────────────────────────────────────────

    def _z_big(self, x: int, y: int):
        self._hline(x,     y,     x + 28, G)
        self._line( x + 28, y,     x,     y + 38, G)
        self._hline(x,     y + 38, x + 28, G)

    def _z_small(self, x: int, y: int):
        self._hline(x,     y,     x + 20, G)
        self._line( x + 20, y,     x,     y + 26, G)
        self._hline(x,     y + 26, x + 20, G)

    # ── animation loops ───────────────────────────────────────

    def _loop_blink(self, expr: Expression):
        while not self._stop.wait(random.uniform(1.5, 3.5)):
            if not self._anim.frame_throttle():
                continue
            np.copyto(self._buf, self._blink[expr])
            self._overlay_effects()
            self._commit(0)
            if self._stop.wait(0.10):
                break
            np.copyto(self._buf, self._base[expr])
            self._overlay_effects()
            self._commit(self._get_fy())
            if random.random() < 0.25:
                if self._stop.wait(0.12):
                    break
                np.copyto(self._buf, self._blink[expr])
                self._overlay_effects()
                self._commit(0)
                if self._stop.wait(0.10):
                    break
                np.copyto(self._buf, self._base[expr])
                self._overlay_effects()
                self._commit(self._get_fy())

    def _loop_sleeping(self):
        z_off = 0.0
        sleep_base = self._base[Expression.SLEEPING]
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                self._stop.wait(0.005)
                continue
            fy = self._get_fy()
            breath = int(3 * math.sin(time.time() * 0.7 * math.pi))
            np.copyto(self._buf, sleep_base)
            for zx, zy_base, small in [(510, 70, False), (570, 100, True), (625, 130, True)]:
                zy = int(zy_base - z_off) + fy + breath
                if 0 <= zy < H - 40:
                    if small:
                        self._z_small(zx, zy)
                    else:
                        self._z_big(zx, zy)
            self._overlay_effects()
            self._commit(fy + breath)
            z_off = (z_off + 2.5) % 60
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            if self._stop.wait(0.6):
                break

    def _loop_speaking(self):
        speak_eyes = self._base[Expression.SPEAKING].copy()
        # Clear mouth area
        speak_eyes[MOUTH_Y - 10:MOUTH_Y + 100, :] = BL
        i = 0
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                continue
            fy = self._get_fy()
            phase = _SPEAK_PHASES[i % len(_SPEAK_PHASES)]
            np.copyto(self._buf, speak_eyes)
            self._buf |= self._speak_mouths[phase]
            self._overlay_effects()
            self._commit(fy)
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            i += 1
            if self._stop.wait(0.09):
                break

    def _loop_thinking(self):
        think_base = self._base[Expression.THINKING]
        dot_xs = [MOUTH_X + 100 + d * 50 for d in range(3)]
        dot_y  = 250
        dot = 0
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                continue
            fy = self._get_fy()
            np.copyto(self._buf, think_base)
            for d in range(dot + 1):
                self._fill_ellipse(dot_xs[d], dot_y, 10, 10, G)
            self._overlay_effects()
            self._commit(fy)
            self._anim.advance_scanlines(330.0)
            dot = (dot + 1) % 3
            if self._stop.wait(0.33):
                break

    def _loop_excited(self):
        excited_base = self._base[Expression.EXCITED]
        bounce_t = 0.0
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                self._stop.wait(0.005)
                continue
            bounce = int(12 * abs(math.sin(bounce_t * 2.5)))
            np.copyto(self._buf, excited_base)
            self._overlay_effects()
            self._commit(self._get_fy() + bounce)
            bounce_t += 0.1
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            if self._stop.wait(0.1):
                break

    def _loop_happy(self):
        happy_base = self._base[Expression.HAPPY]
        bounce_t = 0.0
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                self._stop.wait(0.005)
                continue
            bounce = int(4 * abs(math.sin(bounce_t * 1.5)))
            np.copyto(self._buf, happy_base)
            self._overlay_effects()
            self._commit(self._get_fy() + bounce)
            bounce_t += 0.06
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            if self._stop.wait(0.15):
                break

    def _loop_recording(self):
        rec_base = self._base[Expression.RECORDING]
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                self._stop.wait(0.005)
                continue
            fy = self._get_fy()
            if random.random() < 0.05:
                glitch = np.random.randint(0, 2, (H, W), dtype=np.uint8) * G
                np.copyto(self._buf, glitch)
            else:
                np.copyto(self._buf, rec_base)
            self._overlay_effects()
            self._commit(fy)
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            if self._stop.wait(0.12):
                break

    def _loop_listening(self):
        listen_base = self._base[Expression.LISTENING]
        while not self._stop.is_set():
            if not self._anim.frame_throttle():
                self._stop.wait(0.005)
                continue
            fy = self._get_fy()
            np.copyto(self._buf, listen_base)
            self._overlay_effects()
            self._commit(fy)
            self._anim.advance_scanlines(self._anim._FRAME_MS)
            if self._stop.wait(0.18):
                break
