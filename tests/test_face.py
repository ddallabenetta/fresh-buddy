"""Tests for Face Display Module"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.face.display import OLEDDisplay
from bmo.face.expressions import ExpressionEngine, Expression


class TestOLEDDisplay(unittest.TestCase):
    """Test cases for OLED display driver."""

    def setUp(self):
        """Set up test fixtures."""
        self.display = OLEDDisplay()

    def test_display_initialization(self):
        """Test display initializes without error."""
        self.assertIsNotNone(self.display)
        self.assertEqual(self.display.WIDTH, 800)
        self.assertEqual(self.display.HEIGHT, 480)

    def test_clear(self):
        """Test display clear."""
        # Set some pixels
        self.display.set_pixel(10, 10, OLEDDisplay.WHITE)
        # Clear
        self.display.clear()
        # Verify framebuffer is empty
        fb = self.display.get_framebuffer()
        self.assertEqual(sum(fb), 0)

    def test_set_pixel_bounds(self):
        """Test pixel setting with bounds checking."""
        # Should not error on out of bounds
        self.display.set_pixel(-1, 10, OLEDDisplay.WHITE)
        self.display.set_pixel(200, 10, OLEDDisplay.WHITE)
        self.display.set_pixel(10, -1, OLEDDisplay.WHITE)
        self.display.set_pixel(10, 100, OLEDDisplay.WHITE)

    def test_set_pixel_white(self):
        """Test setting white pixel."""
        self.display.clear()
        self.display.set_pixel(50, 30, OLEDDisplay.WHITE)
        fb = self.display.get_framebuffer()
        self.assertGreater(sum(fb), 0)

    def test_set_pixel_black(self):
        """Test setting black pixel (clearing)."""
        self.display.clear()
        self.display.set_pixel(50, 30, OLEDDisplay.WHITE)
        self.display.set_pixel(50, 30, OLEDDisplay.BLACK)
        # After setting to black, that byte should be 0
        index = 50 + (30 // 8) * 128
        self.assertEqual(self.display._framebuffer[index], 0)

    def test_draw_rect_outline(self):
        """Test drawing rectangle outline."""
        self.display.clear()
        self.display.draw_rect(10, 10, 20, 15, OLEDDisplay.WHITE, fill=False)
        # Just verify no error
        self.display.show()

    def test_draw_rect_fill(self):
        """Test drawing filled rectangle."""
        self.display.clear()
        self.display.draw_rect(10, 10, 10, 10, OLEDDisplay.WHITE, fill=True)
        # Verify some pixels are set
        fb = self.display.get_framebuffer()
        self.assertGreater(sum(fb), 0)

    def test_draw_text(self):
        """Test drawing text."""
        self.display.clear()
        self.display.draw_text(10, 20, "BMO")
        fb = self.display.get_framebuffer()
        # Some pixels should be set
        self.assertGreater(sum(fb), 0)

    def test_framebuffer_size(self):
        """Test framebuffer has correct size."""
        expected_size = 800 * 480  # 384 000 bytes
        self.assertEqual(len(self.display.get_framebuffer()), expected_size)


class TestExpressionEngine(unittest.TestCase):
    """Test cases for expression engine."""

    def setUp(self):
        """Set up test fixtures."""
        self.display = OLEDDisplay()
        self.expressions = ExpressionEngine(self.display)

    def test_expression_enum(self):
        """Test expression enum values."""
        self.assertEqual(Expression.HAPPY.value, "happy")
        self.assertEqual(Expression.SAD.value, "sad")
        self.assertEqual(Expression.CONFUSED.value, "confused")

    def test_show_expression_happy(self):
        """Test showing happy expression."""
        self.expressions.show_expression("happy")
        self.assertEqual(self.expressions.current_expression, Expression.HAPPY)

    def test_show_expression_invalid(self):
        """Test showing invalid expression falls back to neutral."""
        self.expressions.show_expression("nonexistent")
        self.assertEqual(self.expressions.current_expression, Expression.NEUTRAL)

    def test_show_expression_case_insensitive(self):
        """Test expression names are case insensitive."""
        self.expressions.show_expression("HAPPY")
        self.assertEqual(self.expressions.current_expression, Expression.HAPPY)

        self.expressions.show_expression("Sad")
        self.assertEqual(self.expressions.current_expression, Expression.SAD)

    def test_animate_speaking(self):
        """Test speaking animation."""
        # Should not error
        self.expressions.animate_speaking(duration=0.01)

    def test_test_all_expressions(self):
        """Test running through all expressions."""
        # Should not error
        self.expressions.test_all()


class TestDisplayIntegration(unittest.TestCase):
    """Integration tests for display with expressions."""

    def setUp(self):
        """Set up test fixtures."""
        self.display = OLEDDisplay()
        self.expressions = ExpressionEngine(self.display)

    def test_all_expressions_render(self):
        """Test all expressions can render without error."""
        for expr in Expression:
            self.expressions.show_expression(expr.value)
            # Display should have content
            fb = self.display.get_framebuffer()
            self.assertGreater(sum(fb), 0, f"Expression {expr.value} produced empty framebuffer")


if __name__ == "__main__":
    unittest.main()
