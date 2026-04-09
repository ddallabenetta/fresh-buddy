"""Expression Engine for Fresh Buddy Face Animations"""

import logging
import time
import threading
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Expression(Enum):
    """Fresh Buddy facial expressions."""
    HAPPY = "happy"
    SAD = "sad"
    CONFUSED = "confused"
    EXCITED = "excited"
    NEUTRAL = "neutral"
    THINKING = "thinking"
    LISTENING = "listening"
    SLEEPING = "sleeping"
    SPEAKING = "speaking"
    RECORDING = "recording"


class ExpressionEngine:
    """Manages Fresh Buddy facial expressions and animations."""

    def __init__(self, display):
        """
        Initialize expression engine.

        Args:
            display: OLEDDisplay instance
        """
        self.display = display
        self.current_expression = Expression.NEUTRAL
        self._animation_thread: Optional[threading.Thread] = None
        self._stop_animation = threading.Event()
        self._mouth_open = False

    def show_expression(self, expression: str):
        """
        Show a specific expression.

        Args:
            expression: Expression name (happy, sad, confused, etc.)
        """
        try:
            expr = Expression(expression.lower())
        except ValueError:
            logger.warning(f"Unknown expression: {expression}")
            expr = Expression.NEUTRAL

        self.current_expression = expr
        self._render_expression(expr)

        # Start idle animation if needed
        if expr in [Expression.SLEEPING, Expression.THINKING]:
            self._start_idle_animation(expr)

    def _render_expression(self, expression: Expression):
        """Render a static expression to the display."""
        self.display.clear()

        # BMO face dimensions (body is rounded rectangle)
        body_x, body_y = 20, 8
        body_w, body_h = 88, 48

        # Draw BMO body (rounded rectangle)
        self._draw_rounded_rect(body_x, body_y, body_w, body_h, 8)

        # Draw screen area (inner rectangle)
        screen_x, screen_y = body_x + 6, body_y + 6
        screen_w, screen_h = body_w - 12, body_h - 20
        self._draw_rounded_rect(screen_x, screen_y, screen_w, screen_h, 4, fill=True)

        # Draw eyes based on expression
        eye_y = screen_y + 8
        eye_spacing = 18

        if expression == Expression.SLEEPING:
            # Sleeping: closed eyes (lines)
            self._draw_eye_line(screen_x + 18, eye_y + 6, 10)
            self._draw_eye_line(screen_x + 40, eye_y + 6, 10)
        elif expression == Expression.CONFUSED:
            # Confused: one eye open, one closed, eyebrow tilted
            self._draw_eye_open(screen_x + 15, eye_y)
            self._draw_eye_line(screen_x + 37, eye_y + 4, 10)
            # Tilted eyebrow
            self._draw_line(screen_x + 12, eye_y - 4, screen_x + 22, eye_y - 2)
            self._draw_line(screen_x + 34, eye_y - 2, screen_x + 44, eye_y - 6)
        elif expression == Expression.SAD:
            # Sad: droopy eyes
            self._draw_eye_open(screen_x + 15, eye_y + 2)
            self._draw_eye_open(screen_x + 37, eye_y + 2)
            # Sad mouth
            self._draw_sad_mouth(screen_x + 20, screen_y + 22)
        elif expression == Expression.EXCITED:
            # Excited: big eyes, big smile
            self._draw_eye_big(screen_x + 14, eye_y - 2)
            self._draw_eye_big(screen_x + 38, eye_y - 2)
            self._draw_big_smile(screen_x + 18, screen_y + 20)
        elif expression == Expression.SPEAKING:
            # Speaking: animate mouth
            self._draw_eye_open(screen_x + 15, eye_y)
            self._draw_eye_open(screen_x + 37, eye_y)
            if self._mouth_open:
                self._draw_open_mouth(screen_x + 20, screen_y + 20)
            else:
                self._draw_small_smile(screen_x + 22, screen_y + 22)
        elif expression == Expression.RECORDING:
            # Recording: red dot and alert eyes
            self._draw_recording_indicator(screen_x + screen_w - 12, screen_y + 4)
            self._draw_eye_open(screen_x + 15, eye_y)
            self._draw_eye_open(screen_x + 37, eye_y)
            self._draw_flat_mouth(screen_x + 22, screen_y + 22)
        elif expression == Expression.LISTENING:
            # Listening: attentive eyes
            self._draw_eye_attentive(screen_x + 15, eye_y)
            self._draw_eye_attentive(screen_x + 37, eye_y)
            self._draw_small_smile(screen_x + 22, screen_y + 22)
        elif expression == Expression.THINKING:
            # Thinking: looking to side with dots
            self._draw_eye_right(screen_x + 16, eye_y)
            self._draw_eye_right(screen_x + 38, eye_y)
            self._draw_thinking_dots(screen_x + 50, screen_y + 10)
            self._draw_small_smile(screen_x + 22, screen_y + 22)
        else:
            # Neutral/Happy: normal eyes and smile
            self._draw_eye_open(screen_x + 15, eye_y)
            self._draw_eye_open(screen_x + 37, eye_y)
            self._draw_smile(screen_x + 20, screen_y + 22)

        # Draw "Buddy" label at bottom
        self.display.draw_text(screen_x + 24, screen_y + screen_h - 10, "Buddy")

        self.display.show()

    def _draw_rounded_rect(self, x: int, y: int, w: int, h: int, r: int, fill: bool = False):
        """Draw rounded rectangle."""
        if fill:
            for dy in range(h):
                for dx in range(w):
                    # Check if point is inside rounded rect
                    if dx < r:
                        if dy < r:
                            if (dx - r) ** 2 + (dy - r) ** 2 > r ** 2:
                                continue
                        elif dy >= h - r:
                            if (dx - r) ** 2 + (dy - (h - r - 1)) ** 2 > r ** 2:
                                continue
                    elif dx >= w - r:
                        if dy < r:
                            if (dx - (w - r - 1)) ** 2 + (dy - r) ** 2 > r ** 2:
                                continue
                        elif dy >= h - r:
                            if (dx - (w - r - 1)) ** 2 + (dy - (h - r - 1)) ** 2 > r ** 2:
                                continue
                    self.display.set_pixel(x + dx, y + dy)
        else:
            # Draw just the outline
            # Top and bottom arcs
            for i in range(r):
                self.display.set_pixel(x + r - i, y + i)
                self.display.set_pixel(x + w - r + i, y + i)
                self.display.set_pixel(x + r - i, y + h - 1 - i)
                self.display.set_pixel(x + w - r + i, y + h - 1 - i)
            # Top and bottom lines
            for dx in range(r, w - r):
                self.display.set_pixel(x + dx, y)
                self.display.set_pixel(x + dx, y + h - 1)
            # Left and right lines
            for dy in range(r, h - r):
                self.display.set_pixel(x, y + dy)
                self.display.set_pixel(x + w - 1, y + dy)

    def _draw_eye_open(self, x: int, y: int):
        """Draw normal open eye."""
        # Outer eye shape
        self._draw_ellipse(x, y, 8, 6)
        # Pupil
        self._draw_fill(x + 2, y + 1, 4, 4)

    def _draw_eye_big(self, x: int, y: int):
        """Draw big excited eye."""
        self._draw_ellipse(x, y, 10, 8)
        self._draw_fill(x + 3, y + 2, 5, 5)

    def _draw_eye_attentive(self, x: int, y: int):
        """Draw attentive listening eye."""
        self._draw_ellipse(x, y, 7, 5)
        self._draw_fill(x + 2, y + 1, 3, 3)

    def _draw_eye_right(self, x: int, y: int):
        """Draw eye looking to the right."""
        self._draw_ellipse(x, y, 7, 5)
        self._draw_fill(x + 3, y + 1, 3, 3)

    def _draw_eye_line(self, x: int, y: int, length: int):
        """Draw closed eye (horizontal line)."""
        for i in range(length):
            self.display.set_pixel(x + i, y)

    def _draw_ellipse(self, cx: int, cy: int, rx: int, ry: int):
        """Draw ellipse outline."""
        # Simple midpoint ellipse algorithm
        for angle in range(360):
            import math
            rad = math.radians(angle)
            x = int(cx + rx * math.cos(rad))
            y = int(cy + ry * math.sin(rad))
            self.display.set_pixel(x, y)

    def _draw_fill(self, x: int, y: int, w: int, h: int):
        """Draw filled rectangle."""
        for dy in range(h):
            for dx in range(w):
                self.display.set_pixel(x + dx, y + dy)

    def _draw_line(self, x1: int, y1: int, x2: int, y2: int):
        """Draw line using Bresenham's algorithm."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
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

    def _draw_smile(self, x: int, y: int):
        """Draw simple smile."""
        # Arc for smile
        for i in range(16):
            import math
            angle = math.pi * i / 16
            px = int(x + i)
            py = int(y + 4 * math.sin(angle))
            self.display.set_pixel(px, py)

    def _draw_big_smile(self, x: int, y: int):
        """Draw big excited smile."""
        for i in range(20):
            import math
            angle = math.pi * i / 20
            px = int(x + i)
            py = int(y + 6 * math.sin(angle))
            self.display.set_pixel(px, py)

    def _draw_small_smile(self, x: int, y: int):
        """Draw small subtle smile."""
        for i in range(10):
            import math
            angle = math.pi * i / 10
            px = int(x + i)
            py = int(y + 2 * math.sin(angle))
            self.display.set_pixel(px, py)

    def _draw_sad_mouth(self, x: int, y: int):
        """Draw sad frown."""
        for i in range(12):
            import math
            angle = math.pi + math.pi * i / 12
            px = int(x + i)
            py = int(y + 3 * math.sin(angle))
            self.display.set_pixel(px, py)

    def _draw_flat_mouth(self, x: int, y: int):
        """Draw flat line mouth."""
        for i in range(12):
            self.display.set_pixel(x + i, y)

    def _draw_open_mouth(self, x: int, y: int):
        """Draw open mouth for speaking."""
        self._draw_rounded_rect(x, y, 12, 8, 2, fill=True)

    def _draw_recording_indicator(self, x: int, y: int):
        """Draw red recording dot."""
        # Draw red circle
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if dx * dx + dy * dy <= 16:
                    self.display.set_pixel(x + dx, y + dy)

    def _draw_thinking_dots(self, x: int, y: int):
        """Draw thinking animation dots..."""
        for i in range(3):
            self.display.set_pixel(x + i * 6, y)
            self.display.set_pixel(x + i * 6, y + 1)

    def _start_idle_animation(self, expression: Expression):
        """Start idle animation loop."""
        if self._animation_thread and self._animation_thread.is_alive():
            self._stop_animation.set()
            self._animation_thread.join(timeout=0.5)

        self._stop_animation = threading.Event()
        self._animation_thread = threading.Thread(
            target=self._idle_animation_loop,
            args=(expression,),
            daemon=True
        )
        self._animation_thread.start()

    def _idle_animation_loop(self, expression: Expression):
        """Run idle animation (sleeping Z's, thinking dots, etc.)."""
        if expression == Expression.SLEEPING:
            z_offset = 0
            while not self._stop_animation.is_set():
                self.display.clear()
                # Redraw face sleeping
                self._render_static_sleeping()
                # Animate Z's
                self._draw_zzz(70, 15 + z_offset)
                self.display.show()
                time.sleep(1)
                z_offset = (z_offset + 3) % 10

        elif expression == Expression.THINKING:
            dot_phase = 0
            while not self._stop_animation.is_set():
                self.display.clear()
                self._render_static_thinking(dot_phase)
                self.display.show()
                time.sleep(0.5)
                dot_phase = (dot_phase + 1) % 3

    def _render_static_sleeping(self):
        """Render base sleeping face."""
        body_x, body_y = 20, 8
        body_w, body_h = 88, 48
        self._draw_rounded_rect(body_x, body_y, body_w, body_h, 8)
        screen_x, screen_y = body_x + 6, body_y + 6
        screen_w, screen_h = body_w - 12, body_h - 20
        self._draw_rounded_rect(screen_x, screen_y, screen_w, screen_h, 4, fill=True)
        # Closed eyes
        self._draw_eye_line(screen_x + 18, screen_y + 14, 10)
        self._draw_eye_line(screen_x + 40, screen_y + 14, 10)
        self.display.draw_text(screen_x + 24, screen_y + screen_h - 10, "Buddy")

    def _render_static_thinking(self, dot_phase: int):
        """Render thinking face with animated dots."""
        body_x, body_y = 20, 8
        body_w, body_h = 88, 48
        self._draw_rounded_rect(body_x, body_y, body_w, body_h, 8)
        screen_x, screen_y = body_x + 6, body_y + 6
        screen_w, screen_h = body_w - 12, body_h - 20
        self._draw_rounded_rect(screen_x, screen_y, screen_w, screen_h, 4, fill=True)
        # Eyes looking right
        self._draw_eye_right(screen_x + 16, screen_y + 8)
        self._draw_eye_right(screen_x + 38, screen_y + 8)
        # Thinking dots
        for i in range(3):
            if i <= dot_phase:
                self.display.set_pixel(screen_x + 50 + i * 6, screen_y + 10)
                self.display.set_pixel(screen_x + 50 + i * 6, screen_y + 11)
        # Small smile
        self._draw_small_smile(screen_x + 22, screen_y + 22)
        self.display.draw_text(screen_x + 24, screen_y + screen_h - 10, "Buddy")

    def _draw_zzz(self, x: int, y: int):
        """Draw sleeping Z's."""
        z_chars = ["Z", "z", "z"]
        for i, char in enumerate(z_chars):
            offset_y = y - i * 8
            if offset_y > 10:
                self.display.draw_text(x + i * 10, offset_y, char)

    def animate_speaking(self, duration: float = 0.1):
        """Animate mouth for speaking.

        Args:
            duration: Duration of each mouth state in seconds
        """
        self._mouth_open = True
        self._render_expression(Expression.SPEAKING)
        time.sleep(duration)
        self._mouth_open = False
        self._render_expression(Expression.SPEAKING)

    def test_all(self):
        """Run through all expressions for testing."""
        expressions = [
            Expression.HAPPY,
            Expression.SAD,
            Expression.CONFUSED,
            Expression.EXCITED,
            Expression.NEUTRAL,
            Expression.LISTENING,
            Expression.SPEAKING,
            Expression.THINKING,
            Expression.SLEEPING,
            Expression.RECORDING,
        ]

        for expr in expressions:
            logger.info(f"Testing expression: {expr.value}")
            self.show_expression(expr.value)
            time.sleep(1.5)

        self.show_expression("neutral")
        logger.info("Expression test complete")
