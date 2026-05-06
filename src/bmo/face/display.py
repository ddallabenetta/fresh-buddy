"""BMO Face Display Driver — pygame framebuffer renderer for 800×480 HDMI LCD.

Driver strategy
───────────────
  1. Try pygame with the Linux framebuffer (fbcon) → direct /dev/fb0 write,
     no X11 required — works on Jetson Nano, Raspberry Pi, etc.
  2. Fall back to pygame dummy driver for dev / CI without hardware.
  3. Fall back to simulation mode (PNG HTTP server on port 8088).

All drawing goes to a numpy (H×W) back-buffer canvas.  show() copies the
back-buffer to a pygame Surface and blits it to the screen.
"""

import logging
import mmap
import os
import time
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    np = None
    _NUMPY = False

_PYGAME_OK   = False
_PYGAME_MODE = "unavailable"

try:
    import pygame as _pg
    _PYGAME_OK = True
except Exception as e:
    logger.debug("pygame not available: %s", e)


class OLEDDisplay:
    """800×480 BMO face display driven by pygame."""

    WIDTH   = 800
    HEIGHT  = 480
    BLACK   = (0,   0,   0)
    WHITE   = (255, 255, 255)
    GREEN   = (57,  255, 20)
    CYAN    = (0,   255, 255)
    AMBER   = (255, 176, 0)
    MAGENTA = (255, 0,   255)
    INVERSE = None

    # ── face geometry ────────────────────────────────────────────
    BODY_CX, BODY_CY     = 400, 255
    BODY_RX, BODY_RY     = 195, 210
    L_EYE_CX, L_EYE_CY  = 270, 185
    R_EYE_CX, R_EYE_CY  = 530, 185
    MOUTH_CX, MOUTH_CY   = 400, 330

    _DEFAULT_FPS = 30

    def __init__(self, config=None, address: int = 0x3C):
        self.config  = config
        self.address = address
        self._initialized = False
        self._pygame_ok   = False
        self._screen      = None
        self._fb_map = None
        self._fb_virtual_width = 0
        self._fb_virtual_height = 0
        self._fb_stride = 0
        self._fb_bpp = 0

        if _NUMPY:
            self._canvas = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        else:
            self._canvas = None

        self._framebuffer = bytearray(self.WIDTH * self.HEIGHT)
        self._lock = threading.RLock()

        self._target_fps     = self._DEFAULT_FPS
        self._frame_interval = 1.0 / self._DEFAULT_FPS
        self._last_frame_time = 0.0

        self._layers: Dict[str, "np.ndarray"] = {}
        self._layer_visibility: Dict[str, bool] = {}

        self._init_display()

    # ── canvas ───────────────────────────────────────────────────

    @property
    def canvas(self):
        return self._canvas

    # ── init ────────────────────────────────────────────────────

    def _init_display(self):
        global _PYGAME_MODE

        if not _PYGAME_OK:
            logger.warning("pygame not installed — simulation mode")
            self._start_simulation()
            return

        # Try fbcon first (direct framebuffer, no X11)
        for driver in ("fbcon", "kmsdrm", "directfb"):
            try:
                if os.path.exists("/dev/fb0"):
                    os.environ["SDL_FBDEV"] = "/dev/fb0"
                os.environ["SDL_VIDEODRIVER"] = driver
                _pg.init()
                _pg.mouse.set_visible(False)
                self._screen = _pg.display.set_mode(
                    (self.WIDTH, self.HEIGHT), _pg.FULLSCREEN)
                self._pygame_ok = True
                _PYGAME_MODE = driver
                self._initialized = True
                logger.info("pygame/%s (%dx%d)", driver, self.WIDTH, self.HEIGHT)
                return
            except Exception as e:
                _pg.quit()
                logger.debug("SDL_VIDEODRIVER=%s failed: %s", driver, e)

        if self._init_framebuffer():
            _PYGAME_MODE = "framebuffer"
            self._initialized = True
            logger.info(
                "direct framebuffer (%dx%d -> %dx%d)",
                self.WIDTH,
                self.HEIGHT,
                self._fb_virtual_width,
                self._fb_virtual_height,
            )
            return

        # Try dummy (headless dev/CI)
        try:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            _pg.init()
            self._screen = _pg.display.set_mode((self.WIDTH, self.HEIGHT))
            self._pygame_ok = True
            _PYGAME_MODE = "dummy"
            self._initialized = True
            logger.info("pygame/dummy (%dx%d)", self.WIDTH, self.HEIGHT)
            return
        except Exception as e:
            logger.debug("pygame dummy failed: %s", e)

        logger.warning("pygame hardware unavailable — simulation mode")
        self._start_simulation()

    def _init_framebuffer(self) -> bool:
        fb_path = "/dev/fb0"
        try:
            if not os.path.exists(fb_path):
                return False

            with open("/sys/class/graphics/fb0/virtual_size", "r", encoding="utf-8") as f:
                virt_w, virt_h = [int(v) for v in f.read().strip().split(",")]
            with open("/sys/class/graphics/fb0/bits_per_pixel", "r", encoding="utf-8") as f:
                bits_per_pixel = int(f.read().strip())
            with open("/sys/class/graphics/fb0/stride", "r", encoding="utf-8") as f:
                stride = int(f.read().strip())

            if bits_per_pixel != 32:
                logger.warning("Unsupported framebuffer format: %s bpp", bits_per_pixel)
                return False

            fb_size = stride * virt_h
            fb_fd = os.open(fb_path, os.O_RDWR)
            self._fb_map = mmap.mmap(fb_fd, fb_size, mmap.MAP_SHARED, mmap.PROT_WRITE)
            os.close(fb_fd)
            self._fb_virtual_width = virt_w
            self._fb_virtual_height = virt_h
            self._fb_stride = stride
            self._fb_bpp = bits_per_pixel
            return True
        except Exception as e:
            logger.debug("Direct framebuffer init failed: %s", e)
            if self._fb_map is not None:
                self._fb_map.close()
                self._fb_map = None
            return False

    def _start_simulation(self):
        try:
            import os
            port = int(os.environ.get("PREVIEW_PORT", 8088))
            from bmo.face.preview_server import start_preview_server
            start_preview_server(self, port=port)
            logger.info("Simulation mode active (http://localhost:%d/)", port)
        except Exception as e:
            logger.debug("Preview server not started: %s", e)

    # ── animation timing ───────────────────────────────────────────

    def set_animation_fps(self, target_fps: int) -> None:
        target_fps = max(1, min(120, int(target_fps)))
        self._target_fps     = target_fps
        self._frame_interval = 1.0 / target_fps
        logger.debug("Animation FPS → %d", target_fps)

    def get_animation_fps(self) -> int:
        return self._target_fps

    def wait_for_next_frame(self) -> float:
        now     = time.monotonic()
        elapsed = now - self._last_frame_time
        sleep_s = self._frame_interval - elapsed
        if sleep_s > 0:
            time.sleep(sleep_s)
        self._last_frame_time = time.monotonic()
        return time.monotonic() - now

    def flip(self) -> None:
        self.show()

    # ── colour helpers ───────────────────────────────────────────

    def _to_canvas(self, color):
        """Normalise any colour → uint8 canvas value (0=black, >0=lit)."""
        if isinstance(color, tuple):
            r, g, b = color
            return int(0.299 * r + 0.587 * g + 0.114 * b)
        if color is None:
            return 0
        return max(0, min(255, int(color)))

    def _to_rgb(self, color):
        """Normalise any colour → (R, G, B) pygame tuple."""
        if isinstance(color, tuple):
            return color
        if color is None:
            return (0, 0, 0)
        v = max(0, min(255, int(color)))
        return (v, v, v)

    # ── drawing API ───────────────────────────────────────────────

    def clear(self):
        with self._lock:
            if _NUMPY and self._canvas is not None:
                self._canvas[:] = 0
            for i in range(len(self._framebuffer)):
                self._framebuffer[i] = 0

    def set_pixel(self, x: int, y: int, color=WHITE):
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return
        c = self._to_canvas(color)
        with self._lock:
            if _NUMPY and self._canvas is not None:
                self._canvas[y, x] = c
            else:
                self._framebuffer[y * self.WIDTH + x] = c

    def draw_rect(self, x: int, y: int, width: int, height: int,
                  color=WHITE, fill: bool = False):
        c = self._to_canvas(color)
        with self._lock:
            if fill:
                for dy in range(height):
                    for dx in range(width):
                        self.set_pixel(x + dx, y + dy, c)
            else:
                for dx in range(width):
                    self.set_pixel(x + dx, y,              c)
                    self.set_pixel(x + dx, y + height - 1, c)
                for dy in range(height):
                    self.set_pixel(x,          y + dy, c)
                    self.set_pixel(x + width - 1, y + dy, c)

    def draw_glow_rect(self, x: int, y: int, w: int, h: int,
                       color=WHITE, intensity: int = 6) -> None:
        intensity = max(1, min(12, int(intensity)))
        c = self._to_canvas(color)
        with self._lock:
            self.draw_rect(x, y, w, h, c, fill=True)
            for ring in range(1, intensity + 1):
                rx, ry, rw, rh = x - ring, y - ring, w + ring * 2, h + ring * 2
                step = 1 + (ring - 1) // 2
                for dx in range(0, rw, step):
                    self.set_pixel(rx + dx, ry,          c)
                    self.set_pixel(rx + dx, ry + rh - 1, c)
                for dy in range(0, rh, step):
                    self.set_pixel(rx,          ry + dy, c)
                    self.set_pixel(rx + rw - 1, ry + dy, c)

    def draw_ellipse(self, cx: int, cy: int, rx: int, ry: int,
                     color=WHITE, fill: bool = True):
        import math
        c = self._to_canvas(color)
        with self._lock:
            if fill:
                for dy in range(-ry, ry + 1):
                    y = cy + dy
                    if not (0 <= y < self.HEIGHT):
                        continue
                    w = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry) ** 2))) if ry else 0
                    x0, x1 = max(0, cx - w), min(self.WIDTH, cx + w + 1)
                    if _NUMPY and self._canvas is not None:
                        self._canvas[y, x0:x1] = c
                    else:
                        for x in range(x0, x1):
                            self._framebuffer[y * self.WIDTH + x] = c
            else:
                for angle in range(0, 360, 2):
                    rad = math.radians(angle)
                    self.set_pixel(
                        int(cx + rx * math.cos(rad)),
                        int(cy + ry * math.sin(rad)), c)

    def draw_circle(self, cx: int, cy: int, r: int, color=WHITE, fill: bool = False):
        self.draw_ellipse(cx, cy, r, r, color=self._to_canvas(color), fill=fill)

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color=WHITE, width: int = 1):
        import math
        c = self._to_canvas(color)
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        steps = max(1, dx if dx >= dy else dy)
        xs = np.round(np.linspace(x1, x2, steps)).astype(int)
        ys = np.round(np.linspace(y1, y2, steps)).astype(int)
        with self._lock:
            for x, y in zip(xs, ys):
                for w in range(width):
                    self.set_pixel(x, y - width // 2 + w, c)

    def draw_polygon(self, points, color=WHITE, fill: bool = False):
        c = self._to_canvas(color)
        with self._lock:
            if fill:
                xmin = min(p[0] for p in points)
                xmax = max(p[0] for p in points)
                ymin = min(p[1] for p in points)
                ymax = max(p[1] for p in points)
                for y in range(ymin, ymax + 1):
                    for x in range(xmin, xmax + 1):
                        if self._point_in_polygon(x, y, points):
                            self.set_pixel(x, y, c)
            else:
                for i in range(-1, len(points) - 1):
                    self.draw_line(points[i][0], points[i][1],
                                   points[i + 1][0], points[i + 1][1], c)

    def _point_in_polygon(self, x: int, y: int, points) -> bool:
        n = len(points)
        inside = False
        p1x, p1y = points[0]
        for i in range(1, n + 1):
            p2x, p2y = points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def draw_text(self, x: int, y: int, text: str, color=WHITE, font_size: int = 20):
        if not _PYGAME_OK or self._screen is None:
            self._draw_text_numpy(x, y, text, color)
            return
        import pygame
        c = self._to_rgb(color)
        font = pygame.font.Font(pygame.font.get_default_font(), font_size)
        for i, line in enumerate(text.split("\n")):
            surf = font.render(line, False, c)
            self._screen.blit(surf, (x, y + i * (font_size + 4)))

    def _draw_text_numpy(self, x: int, y: int, text: str, color=WHITE):
        scale = 2
        font = {
            'A': [0x7C,0x12,0x11,0x12,0x7C], 'B': [0x7F,0x49,0x49,0x49,0x36],
            'C': [0x3E,0x41,0x41,0x41,0x22], 'D': [0x7F,0x41,0x41,0x22,0x1C],
            'E': [0x7F,0x49,0x49,0x49,0x41], 'F': [0x7F,0x09,0x09,0x09,0x01],
            'G': [0x3E,0x41,0x49,0x49,0x7A], 'H': [0x7F,0x08,0x08,0x08,0x7F],
            'I': [0x00,0x41,0x7F,0x41,0x00], 'J': [0x20,0x40,0x41,0x3F,0x01],
            'K': [0x7F,0x08,0x14,0x22,0x41], 'L': [0x7F,0x40,0x40,0x40,0x40],
            'M': [0x7F,0x02,0x0C,0x02,0x7F], 'N': [0x7F,0x04,0x08,0x10,0x7F],
            'O': [0x3E,0x41,0x41,0x41,0x3E], 'P': [0x7F,0x09,0x09,0x09,0x06],
            'Q': [0x3E,0x41,0x51,0x21,0x5E], 'R': [0x7F,0x09,0x19,0x29,0x46],
            'S': [0x46,0x49,0x49,0x49,0x31], 'T': [0x01,0x01,0x7F,0x01,0x01],
            'U': [0x3F,0x40,0x40,0x40,0x3F], 'V': [0x1F,0x20,0x40,0x20,0x1F],
            'W': [0x3F,0x40,0x38,0x40,0x3F], 'X': [0x63,0x14,0x08,0x14,0x63],
            'Y': [0x07,0x08,0x70,0x08,0x07], 'Z': [0x61,0x51,0x49,0x45,0x43],
            '0': [0x3E,0x51,0x49,0x45,0x3E], '1': [0x00,0x42,0x7F,0x40,0x00],
            '2': [0x42,0x61,0x51,0x49,0x46], '3': [0x21,0x41,0x45,0x4B,0x31],
            '4': [0x18,0x14,0x12,0x7F,0x10], '5': [0x27,0x45,0x45,0x45,0x39],
            '6': [0x3C,0x4A,0x49,0x49,0x30], '7': [0x01,0x71,0x09,0x05,0x03],
            '8': [0x36,0x49,0x49,0x49,0x36], '9': [0x06,0x49,0x49,0x29,0x1E],
            ' ': [0x00,0x00,0x00,0x00,0x00], ':': [0x00,0x36,0x36,0x00,0x00],
            '.': [0x00,0x00,0x00,0x00,0x40], '!': [0x00,0x00,0x7F,0x00,0x00],
            '?': [0x42,0x01,0x7F,0x01,0x40],
        }
        c = self._to_canvas(color)
        with self._lock:
            cx = x
            for char in text.upper():
                if char not in font:
                    cx += 6 * scale
                    continue
                for col, byte in enumerate(font[char]):
                    for row in range(8):
                        if byte & (1 << row):
                            for sy in range(scale):
                                for sx in range(scale):
                                    px = cx + col * scale + sx
                                    py = y + row * scale + sy
                                    if 0 <= px < self.WIDTH and 0 <= py < self.HEIGHT:
                                        self.set_pixel(px, py, c)
                cx += 6 * scale

    def draw_sprite(self, image_path: str, x: int = 0, y: int = 0):
        if not _PYGAME_OK or self._screen is None:
            return
        import pygame
        try:
            sprite = pygame.image.load(image_path)
            self._screen.blit(sprite, (x, y))
        except Exception as e:
            logger.warning("Could not load sprite %s: %s", image_path, e)

    # ── main flush ───────────────────────────────────────────────

    def show(self):
        if not self._initialized:
            return

        if _PYGAME_OK and self._screen is not None:
            import pygame
            with self._lock:
                canvas = self._canvas.copy() if _NUMPY and self._canvas is not None else None
            rgb = np.zeros((self.HEIGHT, self.WIDTH, 3), dtype=np.uint8)
            if canvas is not None:
                lit = canvas > 0
                rgb[lit] = (255, 255, 255)
            surf = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
            self._screen.fill((0, 0, 0))
            self._screen.blit(surf, (0, 0))
            pygame.display.flip()
        elif self._fb_map is not None and _NUMPY and self._canvas is not None:
            with self._lock:
                canvas = self._canvas.copy()
            frame = np.zeros(
                (self._fb_virtual_height, self._fb_virtual_width, 4), dtype=np.uint8
            )
            x_off = max(0, (self._fb_virtual_width - self.WIDTH) // 2)
            y_off = max(0, (self._fb_virtual_height - self.HEIGHT) // 2)
            crop_w = min(self.WIDTH, self._fb_virtual_width)
            crop_h = min(self.HEIGHT, self._fb_virtual_height)
            gray = canvas[:crop_h, :crop_w]
            region = frame[y_off:y_off + crop_h, x_off:x_off + crop_w]
            region[..., 0] = gray
            region[..., 1] = gray
            region[..., 2] = gray
            region[..., 3] = 255
            self._fb_map.seek(0)
            self._fb_map.write(frame.tobytes())
        else:
            logger.debug("Display update (simulation)")

    # ── layer system ─────────────────────────────────────────────

    def get_layer(self, name: str) -> Optional["np.ndarray"]:
        if not _NUMPY:
            raise RuntimeError("Layer support requires numpy")
        if name not in self._layers:
            self._layers[name] = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
            self._layer_visibility[name] = True
        return self._layers[name]

    def set_layer_visibility(self, layer_name: str, visible: bool) -> None:
        self._layer_visibility[layer_name] = bool(visible)

    def composite_layers(self, dest=None) -> Optional["np.ndarray"]:
        if not _NUMPY:
            raise RuntimeError("Layer compositing requires numpy")
        if dest is None:
            dest = self._canvas
        dest[:] = 0
        for name, layer in self._layers.items():
            if self._layer_visibility.get(name, True):
                dest |= layer
        return dest

    # ── debug / preview ─────────────────────────────────────────

    def get_framebuffer(self) -> bytearray:
        with self._lock:
            if _NUMPY and self._canvas is not None:
                return bytearray(self._canvas.tobytes())
            return self._framebuffer or bytearray(self.WIDTH * self.HEIGHT)

    def present_frame(self, frame) -> None:
        """Atomically copy a complete frame into the display back buffer."""
        with self._lock:
            if _NUMPY and self._canvas is not None:
                np.copyto(self._canvas, frame)
            else:
                data = frame.tobytes() if hasattr(frame, "tobytes") else bytes(frame)
                self._framebuffer[:] = data[: len(self._framebuffer)]

    def is_available(self) -> bool:
        return self._initialized

    def pygame_mode(self) -> str:
        return _PYGAME_MODE
