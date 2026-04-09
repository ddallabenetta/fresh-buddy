"""OLED Display Driver for BMO Face"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class OLEDDisplay:
    """SSD1306 OLED display driver for 128x64 display."""

    # Display dimensions
    WIDTH = 128
    HEIGHT = 64

    # Color definitions
    BLACK = 0
    WHITE = 1
    INVERSE = 2

    def __init__(self, config=None, address: int = 0x3C):
        """
        Initialize OLED display.

        Args:
            config: Configuration object
            address: I2C address of the display (default 0x3C)
        """
        self.config = config
        self.address = address
        self._framebuffer = None
        self._initialized = False

        # Try to detect and initialize display
        self._init_display()

    def _init_display(self):
        """Initialize the display hardware."""
        try:
            import smbus2

            # Get I2C bus from config or default
            bus_number = getattr(self.config, 'i2c_bus', 1)
            self._bus = smbus2.SMBus(bus_number)

            # Initialize display with sequence
            self._send_command(0xAE)  # Display off
            self._send_command(0xA4)  # Set entire display on
            self._send_command(0xD3, 0x00)  # Set display offset
            self._send_command(0x40)  # Set display start line
            self._send_command(0xA1)  # Set segment re-map
            self._send_command(0xC8)  # Set COM output scan direction
            self._send_command(0xDA, 0x12)  # Set COM pins
            self._send_command(0x81, 0x7F)  # Set contrast
            self._send_command(0xD5, 0x80)  # Set clock divide
            self._send_command(0xD9, 0xF1)  # Set pre-charge
            self._send_command(0xDB, 0x30)  # Set VCOMH
            self._send_command(0x8D, 0x14)  # Charge pump
            self._send_command(0xAF)  # Display on

            # Initialize framebuffer
            self._framebuffer = bytearray(self.WIDTH * self.HEIGHT // 8)
            self._initialized = True
            logger.info(f"OLED display initialized at 0x{self.address:02X}")

        except (ImportError, IOError) as e:
            logger.warning(f"Display hardware not available: {e}")
            logger.info("Running in simulation mode")
            self._initialized = False
            # Create virtual framebuffer for simulation
            self._framebuffer = bytearray(self.WIDTH * self.HEIGHT // 8)
            self._start_preview_server()

    def _start_preview_server(self):
        """Start HTTP preview server when running in simulation mode."""
        try:
            import os
            port = int(os.environ.get("PREVIEW_PORT", 5000))
            from bmo.face.preview_server import start_preview_server
            start_preview_server(self, port=port)
        except Exception as e:
            logger.debug(f"Preview server not started: {e}")

    def _send_command(self, cmd: int, *args: int):
        """Send a command to the display."""
        if not self._initialized:
            return

        try:
            data = [cmd]
            if args:
                data.extend(args)
            self._bus.write_i2c_block_data(self.address, 0x00, data)
        except IOError as e:
            logger.error(f"Failed to send command 0x{cmd:02X}: {e}")

    def _send_data(self, data: bytes):
        """Send data to the display."""
        if not self._initialized:
            return

        try:
            # Send data in chunks
            chunk_size = 16
            for i in range(0, len(data), chunk_size):
                chunk = list(data[i:i + chunk_size])
                self._bus.write_i2c_block_data(self.address, 0x40, chunk)
        except IOError as e:
            logger.error(f"Failed to send data: {e}")

    def clear(self):
        """Clear the display."""
        if self._framebuffer:
            self._framebuffer = bytearray(len(self._framebuffer))

    def set_pixel(self, x: int, y: int, color: int = WHITE):
        """Set a single pixel."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return

        index = x + (y // 8) * self.WIDTH
        mask = 1 << (y % 8)

        if color == self.WHITE:
            self._framebuffer[index] |= mask
        elif color == self.BLACK:
            self._framebuffer[index] &= ~mask
        else:  # INVERSE
            self._framebuffer[index] ^= mask

    def draw_rect(self, x: int, y: int, width: int, height: int, color: int = WHITE, fill: bool = False):
        """Draw a rectangle."""
        if fill:
            for dy in range(height):
                for dx in range(width):
                    self.set_pixel(x + dx, y + dy, color)
        else:
            # Top and bottom
            for dx in range(width):
                self.set_pixel(x + dx, y, color)
                self.set_pixel(x + dx, y + height - 1, color)
            # Left and right
            for dy in range(height):
                self.set_pixel(x, y + dy, color)
                self.set_pixel(x + width - 1, y + dy, color)

    def draw_text(self, x: int, y: int, text: str, color: int = WHITE):
        """Draw text using built-in font."""
        # Simple 5x7 font for BMO
        font = {
            'A': [0x7C, 0x12, 0x11, 0x12, 0x7C],
            'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
            'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
            'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
            'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
            'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
            'G': [0x3E, 0x41, 0x49, 0x49, 0x7A],
            'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
            'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
            'J': [0x20, 0x40, 0x41, 0x3F, 0x01],
            'K': [0x7F, 0x08, 0x14, 0x22, 0x41],
            'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
            'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F],
            'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
            'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
            'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
            'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E],
            'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
            'S': [0x46, 0x49, 0x49, 0x49, 0x31],
            'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
            'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
            'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
            'W': [0x3F, 0x40, 0x38, 0x40, 0x3F],
            'X': [0x63, 0x14, 0x08, 0x14, 0x63],
            'Y': [0x07, 0x08, 0x70, 0x08, 0x07],
            'Z': [0x61, 0x51, 0x49, 0x45, 0x43],
            '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
            '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
            '2': [0x42, 0x61, 0x51, 0x49, 0x46],
            '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
            '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
            '5': [0x27, 0x45, 0x45, 0x45, 0x39],
            '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
            '7': [0x01, 0x71, 0x09, 0x05, 0x03],
            '8': [0x36, 0x49, 0x49, 0x49, 0x36],
            '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
            ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
            ':': [0x00, 0x36, 0x36, 0x00, 0x00],
        }

        cursor_x = x
        for char in text.upper():
            if char in font:
                char_data = font[char]
                for col in range(5):
                    byte = char_data[col]
                    for row in range(8):
                        if byte & (1 << row):
                            self.set_pixel(cursor_x + col, y + row, color)
                cursor_x += 6  # 5 pixels + 1 space

    def show(self):
        """Send framebuffer to display."""
        if not self._initialized:
            # Simulation mode - just log
            logger.debug("Display update (simulation)")
            return

        # Set page address
        self._send_command(0x22)  # Set page address
        self._send_command(0x00)  # Start page
        self._send_command(0x07)  # End page

        # Set column address
        self._send_command(0x21)  # Set column address
        self._send_command(0x00)  # Start column
        self._send_command(0x7F)  # End column

        # Send framebuffer
        self._send_data(bytes(self._framebuffer))

    def is_available(self) -> bool:
        """Check if display hardware is available."""
        return self._initialized

    def get_framebuffer(self) -> bytearray:
        """Get current framebuffer for debugging."""
        return self._framebuffer or bytearray(1024)
