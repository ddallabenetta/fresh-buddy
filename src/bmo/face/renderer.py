"""BMO Face Renderer - Alternative rendering utilities"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class FaceRenderer:
    """Additional face rendering utilities for BMO."""

    def __init__(self, display):
        """
        Initialize face renderer.

        Args:
            display: OLEDDisplay instance
        """
        self.display = display

    def draw_bmo_face(self, x: int = 20, y: int = 8, size: int = 1):
        """
        Draw complete BMO face at position.

        Args:
            x: X position
            y: Y position
            size: Scale factor (1 = normal)
        """
        # Body
        body_w = 88 * size
        body_h = 48 * size
        self._draw_rounded_rect(x, y, body_w, body_h, 8 * size)

        # Screen
        screen_x = x + 6 * size
        screen_y = y + 6 * size
        screen_w = body_w - 12 * size
        screen_h = body_h - 20 * size
        self._draw_rounded_rect(screen_x, screen_y, screen_w, screen_h, 4 * size, fill=True)

    def _draw_rounded_rect(self, x: int, y: int, w: int, h: int, r: int, fill: bool = False):
        """Draw rounded rectangle helper."""
        self.display.draw_rect(x, y, w, h, fill=fill)

    def draw_mouth(self, x: int, y: int, mouth_type: str = "smile"):
        """
        Draw mouth at position.

        Args:
            x: X position
            y: Y position
            mouth_type: Type of mouth (smile, frown, open, flat)
        """
        if mouth_type == "smile":
            for i in range(16):
                import math
                px = x + i
                py = int(y + 4 * math.sin(math.pi * i / 16))
                self.display.set_pixel(px, py)
        elif mouth_type == "frown":
            for i in range(12):
                import math
                px = x + i
                py = int(y + 3 * math.sin(math.pi + math.pi * i / 12))
                self.display.set_pixel(px, py)
        elif mouth_type == "open":
            self.display.draw_rect(x, y, 12, 8, fill=True)
        elif mouth_type == "flat":
            for i in range(12):
                self.display.set_pixel(x + i, y)

    def draw_eyes(self, x: int, y: int, eye_type: str = "open"):
        """
        Draw eyes at position.

        Args:
            x: X position of left eye
            y: Y position
            eye_type: Type of eyes (open, closed, big, happy)
        """
        spacing = 22

        if eye_type == "open":
            self._draw_eye(x, y, 8, 6)
            self._draw_eye(x + spacing, y, 8, 6)
        elif eye_type == "closed":
            for i in range(10):
                self.display.set_pixel(x + i, y + 6)
                self.display.set_pixel(x + spacing + i, y + 6)
        elif eye_type == "big":
            self._draw_eye(x - 1, y - 2, 10, 8)
            self._draw_eye(x + spacing - 1, y - 2, 10, 8)
        elif eye_type == "happy":
            # Happy arc eyes
            for i in range(8):
                import math
                angle = math.pi * i / 8
                lx = int(x + 4 + 4 * math.cos(angle + math.pi))
                ly = int(y + 4 - 4 * math.sin(angle))
                rx = int(x + spacing + 4 + 4 * math.cos(angle + math.pi))
                ry = int(y + 4 - 4 * math.sin(angle))
                self.display.set_pixel(lx, ly)
                self.display.set_pixel(rx, ry)

    def _draw_eye(self, cx: int, cy: int, rx: int, ry: int):
        """Draw ellipse eye."""
        import math
        for angle in range(360):
            rad = math.radians(angle)
            x = int(cx + rx * math.cos(rad))
            y = int(cy + ry * math.sin(rad))
            self.display.set_pixel(x, y)

    def draw_speaker_icon(self, x: int, y: int):
        """Draw small speaker/sound icon."""
        # Simple speaker shape
        self.display.draw_rect(x, y + 2, 3, 4)
        self.display.set_pixel(x + 3, y)
        self.display.set_pixel(x + 4, y + 1)
        self.display.set_pixel(x + 4, y + 6)
        self.display.set_pixel(x + 3, y + 7)

    def draw_recording_dot(self, x: int, y: int, color: int = 1):
        """Draw recording indicator dot."""
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    self.display.set_pixel(x + dx, y + dy, color)
