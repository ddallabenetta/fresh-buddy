"""OLED Display Driver for BMO Face"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    np = None
    _NUMPY = False


class OLEDDisplay:
    """SSD1306 OLED display driver for 128x64 display."""

    WIDTH  = 128
    HEIGHT = 64
    BLACK  = 0
    WHITE  = 1
    INVERSE = 2

    def __init__(self, config=None, address: int = 0x3C):
        self.config  = config
        self.address = address
        self._initialized = False

        # Primary buffer: numpy (H×W) pixel canvas when available.
        # show() converts to SSD1306 column-major bytes at flush time.
        if _NUMPY:
            self._canvas = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        else:
            self._canvas = None
        # Fallback bytearray in SSD1306 format (used when numpy absent or for I2C send).
        self._framebuffer = bytearray(self.WIDTH * self.HEIGHT // 8)

        self._init_display()

    # ── canvas access ────────────────────────────────────────────

    @property
    def canvas(self):
        """Direct numpy (H×W) canvas; None if numpy unavailable."""
        return self._canvas

    # ── hardware init ────────────────────────────────────────────

    def _init_display(self):
        try:
            import smbus2
            bus_number = getattr(self.config, 'i2c_bus', 1)
            self._bus = smbus2.SMBus(bus_number)

            self._send_command(0xAE)        # Display off
            self._send_command(0xA4)        # Set entire display on
            self._send_command(0xD3, 0x00)  # Display offset
            self._send_command(0x40)        # Start line
            self._send_command(0xA1)        # Segment re-map
            self._send_command(0xC8)        # COM scan direction
            self._send_command(0xDA, 0x12)  # COM pins
            self._send_command(0x81, 0x7F)  # Contrast
            self._send_command(0xD5, 0x80)  # Clock divide
            self._send_command(0xD9, 0xF1)  # Pre-charge
            self._send_command(0xDB, 0x30)  # VCOMH
            self._send_command(0x8D, 0x14)  # Charge pump
            self._send_command(0xAF)        # Display on

            self._initialized = True
            logger.info("OLED display initialized at 0x%02X", self.address)

        except (ImportError, IOError) as e:
            logger.warning("Display hardware not available: %s", e)
            logger.info("Running in simulation mode")
            self._initialized = False
            self._start_preview_server()

    def _start_preview_server(self):
        try:
            import os
            port = int(os.environ.get("PREVIEW_PORT", 5000))
            from bmo.face.preview_server import start_preview_server
            start_preview_server(self, port=port)
        except Exception as e:
            logger.debug("Preview server not started: %s", e)

    def _send_command(self, cmd: int, *args: int):
        if not self._initialized:
            return
        try:
            data = [cmd, *args]
            self._bus.write_i2c_block_data(self.address, 0x00, data)
        except IOError as e:
            logger.error("Failed to send command 0x%02X: %s", cmd, e)

    def _send_data(self, data: bytes):
        if not self._initialized:
            return
        try:
            chunk_size = 16
            for i in range(0, len(data), chunk_size):
                chunk = list(data[i:i + chunk_size])
                self._bus.write_i2c_block_data(self.address, 0x40, chunk)
        except IOError as e:
            logger.error("Failed to send data: %s", e)

    # ── public drawing API ───────────────────────────────────────

    def clear(self):
        if _NUMPY and self._canvas is not None:
            self._canvas[:] = 0
        else:
            for i in range(len(self._framebuffer)):
                self._framebuffer[i] = 0

    def set_pixel(self, x: int, y: int, color: int = WHITE):
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return
        if _NUMPY and self._canvas is not None:
            self._canvas[y, x] = 1 if color != self.BLACK else 0
        else:
            index = x + (y // 8) * self.WIDTH
            mask  = 1 << (y % 8)
            if color == self.WHITE:
                self._framebuffer[index] |= mask
            elif color == self.BLACK:
                self._framebuffer[index] &= ~mask
            else:
                self._framebuffer[index] ^= mask

    def draw_rect(self, x: int, y: int, width: int, height: int,
                  color: int = WHITE, fill: bool = False):
        if fill:
            for dy in range(height):
                for dx in range(width):
                    self.set_pixel(x + dx, y + dy, color)
        else:
            for dx in range(width):
                self.set_pixel(x + dx, y, color)
                self.set_pixel(x + dx, y + height - 1, color)
            for dy in range(height):
                self.set_pixel(x, y + dy, color)
                self.set_pixel(x + width - 1, y + dy, color)

    def draw_text(self, x: int, y: int, text: str, color: int = WHITE):
        """Draw text using a minimal 5×7 bitmap font."""
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
        }
        cursor_x = x
        for char in text.upper():
            if char in font:
                for col, byte in enumerate(font[char]):
                    for row in range(8):
                        if byte & (1 << row):
                            self.set_pixel(cursor_x + col, y + row, color)
                cursor_x += 6

    def show(self):
        """Convert canvas to SSD1306 format and flush to hardware (or simulation)."""
        if _NUMPY and self._canvas is not None:
            fb_bytes = self._canvas_to_ssd1306()
        else:
            fb_bytes = bytes(self._framebuffer)

        if not self._initialized:
            logger.debug("Display update (simulation)")
            return

        self._send_command(0x22)
        self._send_command(0x00)
        self._send_command(0x07)
        self._send_command(0x21)
        self._send_command(0x00)
        self._send_command(0x7F)
        self._send_data(fb_bytes)

    # ── internal conversion ──────────────────────────────────────

    def _canvas_to_ssd1306(self) -> bytes:
        """Vectorized (H×W) numpy canvas → SSD1306 column-major bytes.

        Layout: byte at index col + page*128 encodes 8 vertical pixels of
        column `col` in page `page`, LSB = topmost row of the page.
        """
        # Reshape (64, 128) → (8_pages, 8_bits, 128_cols)
        p  = self._canvas.reshape(8, 8, self.WIDTH)
        fb = np.zeros((8, self.WIDTH), dtype=np.uint8)
        for bit in range(8):
            fb |= (p[:, bit, :] << bit)
        return bytes(fb.flatten())

    # ── debug / preview ──────────────────────────────────────────

    def get_framebuffer(self) -> bytearray:
        """Return current frame as SSD1306 bytes (used by preview server)."""
        if _NUMPY and self._canvas is not None:
            return bytearray(self._canvas_to_ssd1306())
        return self._framebuffer or bytearray(1024)

    def is_available(self) -> bool:
        return self._initialized
