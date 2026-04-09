"""Expression Engine for Fresh Buddy — cute face with Matrix-green alive animations."""

import logging
import math
import random
import time
import threading
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Display dimensions
W, H = 128, 64

# Face layout — large expressive eyes, centered mouth
L_EYE   = (32, 21)   # left eye center (x, y)
R_EYE   = (96, 21)   # right eye center
EYE_RX  = 11         # eye x-radius
EYE_RY  = 13         # eye y-radius
PUPIL_R = 5          # pupil radius
MOUTH_X = 64         # mouth horizontal center
MOUTH_Y = 44         # mouth top y


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


class ExpressionEngine:
    """Manages Fresh Buddy facial expressions and alive animations."""

    def __init__(self, display):
        self.display   = display
        self.current   = Expression.NEUTRAL
        self._stop     = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── public API ───────────────────────────────────────────────

    def show_expression(self, name: str):
        try:
            expr = Expression(name.lower())
        except ValueError:
            logger.warning("Unknown expression: %s", name)
            expr = Expression.NEUTRAL
        self._switch(expr)

    def animate_speaking(self, duration: float = 0.1):
        self._draw_frame(self.current, mouth_override="open")
        time.sleep(duration)
        self._draw_frame(self.current)

    def test_all(self):
        for expr in Expression:
            logger.info("Testing: %s", expr.value)
            self._switch(expr)
            time.sleep(2.0)
        self._switch(Expression.NEUTRAL)

    # ── switching & animation dispatch ───────────────────────────

    def _switch(self, expr: Expression):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._stop.clear()
        self.current = expr
        self._draw_frame(expr)

        loops = {
            Expression.SLEEPING: self._loop_sleeping,
            Expression.SPEAKING: self._loop_speaking,
            Expression.THINKING: self._loop_thinking,
        }
        fn = loops.get(expr, lambda: self._loop_blink(expr))
        self._thread = threading.Thread(target=fn, daemon=True)
        self._thread.start()

    # ── frame renderer ───────────────────────────────────────────

    def _draw_frame(self, expr: Expression,
                    blink: bool = False,
                    mouth_override: str = None,
                    think_dots: int = 0):
        self.display.clear()
        self._draw_eyes(expr, blink=blink)
        self._draw_mouth(expr, override=mouth_override)
        if think_dots:
            for d in range(think_dots):
                self._fill_ellipse(MOUTH_X + 22 + d * 8, 41, 2, 2)
        self.display.show()

    # ── eye drawing ──────────────────────────────────────────────

    def _draw_eyes(self, expr: Expression, blink: bool = False):
        for idx, (cx, cy) in enumerate((L_EYE, R_EYE)):
            if blink:
                self._eye_blink(cx, cy)
            elif expr == Expression.HAPPY:
                self._eye_happy(cx, cy)
            elif expr == Expression.SAD:
                self._eye_sad(cx, cy)
            elif expr == Expression.EXCITED:
                self._eye_big(cx, cy)
            elif expr == Expression.SLEEPING:
                self._eye_sleeping(cx, cy)
            elif expr == Expression.CONFUSED:
                if idx == 0:
                    self._eye_normal(cx, cy)
                    self._draw_brow(cx, cy, tilt=True)
                else:
                    self._eye_squint(cx, cy)
                    self._draw_brow(cx, cy, raised=True)
            elif expr == Expression.THINKING:
                self._eye_look_side(cx, cy, shift=+4)
            elif expr == Expression.RECORDING:
                self._eye_wide(cx, cy)
            else:
                # NEUTRAL, LISTENING, SPEAKING
                self._eye_normal(cx, cy)

    def _fill_ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int = 1):
        for dy in range(-ry, ry + 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry) ** 2)))
            for dx in range(-w, w + 1):
                x = cx + dx
                if 0 <= x < W:
                    self.display.set_pixel(x, y, color)

    def _eye_normal(self, cx: int, cy: int):
        """Filled oval eye with dark pupil and shine dot."""
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY)
        self._fill_ellipse(cx, cy, PUPIL_R, PUPIL_R, 0)
        self.display.set_pixel(cx - 3, cy - 5)  # shine

    def _eye_big(self, cx: int, cy: int):
        """Larger eye for excitement."""
        self._fill_ellipse(cx, cy, EYE_RX + 2, EYE_RY + 2)
        self._fill_ellipse(cx, cy, PUPIL_R + 1, PUPIL_R + 1, 0)
        self.display.set_pixel(cx - 3, cy - 6)

    def _eye_wide(self, cx: int, cy: int):
        """Wide alert eye (recording)."""
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY + 3)
        self._fill_ellipse(cx, cy - 1, PUPIL_R - 1, PUPIL_R - 1, 0)
        self.display.set_pixel(cx - 3, cy - 6)

    def _eye_happy(self, cx: int, cy: int):
        """Upper-half filled arch  ∩  — happy squint."""
        for dy in range(-EYE_RY, 1):
            y = cy + dy
            if not (0 <= y < H):
                continue
            w = int(EYE_RX * math.sqrt(max(0.0, 1.0 - (dy / EYE_RY) ** 2)))
            for dx in range(-w, w + 1):
                x = cx + dx
                if 0 <= x < W:
                    self.display.set_pixel(x, y)

    def _eye_sad(self, cx: int, cy: int):
        """Normal eye with inner sad brow tilted downward."""
        self._fill_ellipse(cx, cy + 2, EYE_RX - 1, EYE_RY - 2)
        self._fill_ellipse(cx, cy + 2, PUPIL_R - 1, PUPIL_R - 1, 0)
        self._draw_line(cx - 5, cy - 9, cx + 3, cy - 6)  # drooping brow

    def _eye_look_side(self, cx: int, cy: int, shift: int = 0):
        """Eye with pupil offset to one side."""
        self._fill_ellipse(cx, cy, EYE_RX, EYE_RY)
        self._fill_ellipse(cx + shift, cy, PUPIL_R, PUPIL_R, 0)
        self.display.set_pixel(cx + shift - 2, cy - 4)

    def _eye_blink(self, cx: int, cy: int):
        """Closed eye — three horizontal lines."""
        for dy in range(-1, 2):
            self._draw_line(cx - EYE_RX + 2, cy + dy, cx + EYE_RX - 2, cy + dy)

    def _eye_sleeping(self, cx: int, cy: int):
        """Sleeping closed arc — U-shaped eyelid."""
        for dx in range(-EYE_RX, EYE_RX + 1):
            t = dx / EYE_RX
            y_off = int((EYE_RY // 2) * t * t)
            y = cy + y_off
            if 0 <= y < H:
                self.display.set_pixel(cx + dx, y)
                self.display.set_pixel(cx + dx, y + 1)

    def _eye_squint(self, cx: int, cy: int):
        """Half-closed squint for confused expression."""
        self._fill_ellipse(cx, cy + 3, EYE_RX - 2, EYE_RY // 2)
        self._fill_ellipse(cx, cy + 3, PUPIL_R - 2, PUPIL_R - 2, 0)

    def _draw_brow(self, cx: int, cy: int, tilt: bool = False, raised: bool = False):
        by = cy - EYE_RY - 3
        if tilt:
            self._draw_line(cx - 7, by, cx + 3, by + 4)
        elif raised:
            self._draw_line(cx - 5, by - 4, cx + 5, by - 3)

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
        kind = override or self._MOUTH_MAP.get(expr, "smile")
        cx, y = MOUTH_X, MOUTH_Y
        if   kind == "smile":       self._m_smile(cx, y, w=12, h=6, thick=2)
        elif kind == "big_smile":   self._m_smile(cx, y, w=16, h=8, thick=2)
        elif kind == "small_smile": self._m_smile(cx, y, w=8,  h=3, thick=1)
        elif kind == "frown":       self._m_frown(cx, y)
        elif kind == "open_happy":  self._m_open_happy(cx, y)
        elif kind == "open":        self._m_open(cx, y)
        elif kind == "wavy":        self._m_wavy(cx, y)
        elif kind == "flat":
            self._draw_line(cx - 8, y, cx + 8, y)
            self._draw_line(cx - 8, y + 1, cx + 8, y + 1)
        elif kind == "oval":
            self._fill_ellipse(cx, y + 4, 7, 5)
            self._fill_ellipse(cx, y + 4, 4, 3, 0)
        elif kind == "tiny":
            self._draw_line(cx - 4, y, cx + 4, y)

    def _m_smile(self, cx: int, y: int, w: int = 12, h: int = 6, thick: int = 2):
        for i in range(-w, w + 1):
            py = y + int(h * (i / w) ** 2)
            for t in range(thick):
                self.display.set_pixel(cx + i, py + t)

    def _m_frown(self, cx: int, y: int):
        for i in range(-12, 13):
            py = y + 6 - int(6 * (i / 12) ** 2)
            self.display.set_pixel(cx + i, py)
            self.display.set_pixel(cx + i, py + 1)

    def _m_open_happy(self, cx: int, y: int):
        """Big open mouth: outer lip fill, dark opening, teeth stripe, tongue."""
        # 1. Outer lips (green filled ellipse)
        self._fill_ellipse(cx, y + 8, 15, 9)
        # 2. Inner mouth opening (black)
        self._fill_ellipse(cx, y + 9, 11, 6, 0)
        # 3. Teeth stripe — redraw green on top of inner black
        for dx in range(-9, 10):
            for dy in range(3):
                self.display.set_pixel(cx + dx, y + 3 + dy)
        # 4. Tongue — green bump at bottom of opening
        self._fill_ellipse(cx, y + 14, 7, 3)

    def _m_open(self, cx: int, y: int):
        """Simple open O mouth for speaking."""
        self._fill_ellipse(cx, y + 5, 9, 6)
        self._fill_ellipse(cx, y + 5, 6, 3, 0)

    def _m_wavy(self, cx: int, y: int):
        for i in range(-10, 11):
            py = y + int(2 * math.sin(i * math.pi / 5))
            self.display.set_pixel(cx + i, py)
            self.display.set_pixel(cx + i, py + 1)

    # ── utility drawing ──────────────────────────────────────────

    def _draw_line(self, x1: int, y1: int, x2: int, y2: int):
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            self.display.set_pixel(x1, y1)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    # ── animation loops ──────────────────────────────────────────

    def _loop_blink(self, expr: Expression):
        """Randomly blink every 3-6 seconds to feel alive."""
        while not self._stop.wait(random.uniform(3.0, 6.0)):
            self._draw_frame(expr, blink=True)
            if self._stop.wait(0.12):
                break
            self._draw_frame(expr)

    def _loop_sleeping(self):
        """Animate floating Z's while sleeping."""
        z_offset = 0.0
        while not self._stop.is_set():
            self.display.clear()
            self._draw_eyes(Expression.SLEEPING)
            self._draw_mouth(Expression.SLEEPING)
            for i, ch in enumerate(("Z", "z", "z")):
                zx = 80 + i * 12
                zy = int(12 - z_offset + i * 7)
                if 2 <= zy < H - 8:
                    self.display.draw_text(zx, zy, ch)
            self.display.show()
            z_offset = (z_offset + 1.5) % 20
            if self._stop.wait(0.8):
                break

    def _loop_speaking(self):
        """Cycle mouth shapes to animate speaking."""
        phases = ("small_smile", "open", "open", "small_smile", "open", "small_smile")
        i = 0
        while not self._stop.wait(0.13):
            self.display.clear()
            self._draw_eyes(Expression.SPEAKING)
            self._draw_mouth(Expression.SPEAKING, override=phases[i % len(phases)])
            self.display.show()
            i += 1

    def _loop_thinking(self):
        """Animate ellipsis dots while thinking."""
        dot = 0
        while not self._stop.wait(0.45):
            self._draw_frame(Expression.THINKING, think_dots=dot + 1)
            dot = (dot + 1) % 3
