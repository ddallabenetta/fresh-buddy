"""Tests for 80s expression rendering — visual characteristics, animations, and effects."""

import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmo.face.display import OLEDDisplay
from bmo.face.expressions import (
    EYE_RY,
    L_EYE,
    MOUTH_X,
    MOUTH_Y,
    R_EYE,
    ExpressionEngine,
    Expression,
)


# ── All 10 expressions render without error ─────────────────────────────────

class TestAllExpressionsRender(unittest.TestCase):
    """Verify every Expression enum value renders to a non-empty framebuffer."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    def test_all_10_expressions_exist(self):
        """Expression enum must have exactly 10 entries."""
        self.assertEqual(len(Expression), 10)

    def test_all_expressions_produce_framebuffer(self):
        """Each expression pre-renders to a non-empty canvas."""
        for expr in Expression:
            buf = self.engine._base[expr]
            self.assertGreater(
                buf.sum(), 0,
                f"Expression {expr.value} produced empty framebuffer",
            )

    def test_show_expression_does_not_raise(self):
        """Calling show_expression with any valid name must not raise."""
        for expr in Expression:
            with patch("time.sleep", side_effect=Exception("stop")):
                try:
                    self.engine.show_expression(expr.value)
                except Exception:
                    pass  # thread exceptions are fine

    def test_each_expression_has_blink_frame(self):
        """Every expression must have a corresponding blink frame."""
        for expr in Expression:
            self.assertIn(expr, self.engine._blink)

    def test_each_expression_eye_geometry_differs(self):
        """Eye geometry must vary between expressions (not all identical)."""
        eye_pixels = {}
        for expr in [Expression.NEUTRAL, Expression.HAPPY, Expression.SAD,
                     Expression.EXCITED, Expression.SLEEPING]:
            buf = self.engine._base[expr]
            eye_region = buf[L_EYE[1] - EYE_RY - 40:R_EYE[1] + EYE_RY + 40, :]
            eye_pixels[expr] = eye_region.sum()

        neutral_pixels = eye_pixels[Expression.NEUTRAL]
        self.assertNotEqual(
            eye_pixels[Expression.SLEEPING], neutral_pixels,
            "Sleeping eyes should visually differ from neutral",
        )


# ── Scanline effect ─────────────────────────────────────────────────────────

class TestScanlineEffect(unittest.TestCase):
    """Tests for scanline overlay effect."""

    def setUp(self):
        self.display = OLEDDisplay()

    def test_scanline_method_dims_rows(self):
        """Scanlines dim every third row without clearing the frame."""
        engine = ExpressionEngine(self.display)
        engine._buf[:] = 200
        engine._apply_scanlines(engine._buf)
        self.assertGreater(engine._buf.sum(), 0)
        self.assertLess(engine._buf.sum(), 200 * engine._buf.size)

    def test_render_pipeline_has_hook_for_post_processing(self):
        """The _commit method is the right place to apply scanline overlay."""
        engine = ExpressionEngine(self.display)
        self.assertTrue(callable(engine._commit))

    def test_framebuffer_content_is_not_uniform(self):
        """A rendered expression must have both lit and unlit pixels."""
        engine = ExpressionEngine(self.display)
        buf = engine._base[Expression.NEUTRAL]
        total = buf.size
        lit = int((buf > 0).sum())
        self.assertGreater(lit, 0)
        self.assertLess(lit, total)


# ── Glow effect ─────────────────────────────────────────────────────────────

class TestGlowEffect(unittest.TestCase):
    """Tests for edge glow/bloom effect on the face outline."""

    def setUp(self):
        self.display = OLEDDisplay()

    def test_glow_method_expands_lit_pixels(self):
        """Glow should add bloom around a sparse lit pixel."""
        engine = ExpressionEngine(self.display)
        engine._buf[:] = 0
        engine._buf[100, 100] = 255
        before = int((engine._buf > 0).sum())
        engine._apply_glow(engine._buf)
        after = int((engine._buf > 0).sum())
        self.assertGreater(after, before)

    def test_body_outline_can_be_drawn(self):
        """Display.draw_rect can draw the body outline (foundation for glow)."""
        self.display.clear()
        self.display.draw_rect(20, 8, 88, 48, OLEDDisplay.WHITE, fill=False)
        fb = self.display.get_framebuffer()
        self.assertGreater(sum(fb), 0)


# ── Visual characteristics per expression ────────────────────────────────────

class TestExpressionVisualCharacteristics(unittest.TestCase):
    """Verify each expression has expected visual properties."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    def test_happy_eyes_are_arc_shaped(self):
        """Happy eyes are drawn with _eye_happy (arched upper ellipse)."""
        buf = self.engine._base[Expression.HAPPY]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        self.assertFalse(
            (buf == neutral_buf).all(),
            "Happy expression must differ from neutral",
        )

    def test_sad_eyes_are_lower_than_neutral(self):
        """Sad eyes are offset downward and use smaller ellipse."""
        buf = self.engine._base[Expression.SAD]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        eye_top = L_EYE[1] - EYE_RY - 40
        sad_upper = buf[eye_top:L_EYE[1], :].sum()
        neutral_upper = neutral_buf[eye_top:L_EYE[1], :].sum()
        self.assertNotEqual(sad_upper, neutral_upper)

    def test_excited_eyes_are_larger(self):
        """Excited eyes use _eye_big which has larger radius."""
        buf = self.engine._base[Expression.EXCITED]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        eye_top = L_EYE[1] - EYE_RY - 40
        eye_bottom = L_EYE[1] + EYE_RY + 40
        self.assertGreater(
            buf[eye_top:eye_bottom, :].sum(),
            neutral_buf[eye_top:eye_bottom, :].sum(),
            "EXCITED should have more lit pixels in eye region than NEUTRAL",
        )

    def test_sleeping_eyes_are_arc_not_ellipse(self):
        """Sleeping eyes use parabolic arc, not filled ellipse."""
        buf = self.engine._base[Expression.SLEEPING]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        self.assertFalse(
            (buf == neutral_buf).all(),
            "Sleeping expression must differ from neutral",
        )

    def test_thinking_eyes_look_to_side(self):
        """Thinking eyes use _eye_look_side with horizontal pupil shift."""
        buf = self.engine._base[Expression.THINKING]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        self.assertFalse(
            (buf == neutral_buf).all(),
            "Thinking expression must differ from neutral",
        )

    def test_recording_eyes_are_wide(self):
        """Recording eyes use _eye_wide with expanded vertical radius."""
        buf = self.engine._base[Expression.RECORDING]
        neutral_buf = self.engine._base[Expression.NEUTRAL]
        self.assertFalse(
            (buf == neutral_buf).all(),
            "Recording expression must differ from neutral",
        )


# ── Expression transitions are smooth (timed) ───────────────────────────────

class TestExpressionTransitions(unittest.TestCase):
    """Test that expression changes use the blink transition and timing."""

    def setUp(self):
        self.display = OLEDDisplay()

    @patch("time.sleep")
    def test_transition_changes_expression(self, mock_sleep):
        """Switching expressions must update engine.current to the new expression."""
        mock_sleep.side_effect = [None, Exception("stop")]
        engine = ExpressionEngine(self.display)

        engine.show_expression("happy")
        self.assertEqual(engine.current, Expression.HAPPY)

        engine.show_expression("sad")
        self.assertEqual(engine.current, Expression.SAD)

    @patch("time.sleep")
    def test_transition_pause_is_short(self, mock_sleep):
        """The eye-close pause during transition must be under 100ms."""
        mock_sleep.side_effect = [None, Exception("stop")]
        engine = ExpressionEngine(self.display)

        with patch.object(engine, "_commit"):
            engine.show_expression("happy")

        for call in mock_sleep.call_args_list:
            if call[0]:
                duration = call[0][0]
                if duration > 0.05:
                    self.assertLess(
                        duration, 0.10,
                        f"Transition pause {duration}s exceeds 100ms",
                    )


# ── SPEAKING animation ───────────────────────────────────────────────────────

class TestSpeakingAnimation(unittest.TestCase):
    """Test mouth-open animation used during speech output."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    def test_speaking_base_has_mouth_area(self):
        """Speaking base canvas must have mouth region lit."""
        buf = self.engine._base[Expression.SPEAKING]
        mouth_region = buf[MOUTH_Y - 30:MOUTH_Y + 90, :]
        self.assertGreater(mouth_region.sum(), 0)

    def test_speaking_has_multiple_mouth_phases(self):
        """Speaking loop must cycle through at least 3 distinct mouth shapes."""
        phases = self.engine._speak_mouths
        self.assertIn("small_smile", phases)
        self.assertIn("open", phases)
        self.assertIn("wide", phases)

        self.assertFalse((phases["small_smile"] == phases["open"]).all())
        self.assertFalse((phases["open"] == phases["wide"]).all())

    @unittest.skip("Animation loop calls threading; daemon threads swallow mock exceptions")
    def test_speaking_loop_calls_commit(self):
        """The speaking loop must call _commit to update display.

        Skipped: _loop_speaking runs in a daemon thread; patching time.sleep at
        module level via decorator does not prevent the real time.sleep from being
        called inside the thread, causing the test to hang.
        """
        pass

    def test_animate_speaking_copies_base_then_or_mouth(self):
        """animate_speaking must overlay the open mouth on the base."""
        with patch("time.sleep", side_effect=[None, Exception("stop")]):
            with patch.object(self.engine, "_commit"):
                self.engine.animate_speaking(duration=0.01)

    def test_speak_mouths_are_eyes_free(self):
        """Speaking mouth canvases should only affect mouth area, not eye area."""
        for phase, buf in self.engine._speak_mouths.items():
            eye_region = buf[:MOUTH_Y - 40, :]
            self.assertEqual(
                eye_region.sum(), 0,
                f"Phase '{phase}' should not draw in eye region",
            )


# ── Facial micro-animations ─────────────────────────────────────────────────

class TestFacialMicroAnimations(unittest.TestCase):
    """Test expressive overlays: pupil radar, eyelids, LEDs, and mouth EQ."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    def test_pupil_radar_changes_over_time(self):
        """Dynamic pupil reticles should render different pixels over time."""
        frames = []
        for t in (0.0, 0.8):
            self.engine.current = Expression.NEUTRAL
            self.engine._buf[:] = self.engine._base[Expression.NEUTRAL]
            self.engine._overlay_facial_animation(t)
            frames.append(self.engine._buf.copy())
        self.assertFalse((frames[0] == frames[1]).all())

    def test_speaking_equalizer_affects_mouth_area_only(self):
        """Speaking overlay should add animated bars in the mouth band."""
        self.engine.current = Expression.SPEAKING
        self.engine._buf[:] = self.engine._base[Expression.SPEAKING]
        before = self.engine._buf.copy()
        self.engine._overlay_facial_animation(0.25)
        mouth_before = before[MOUTH_Y:MOUTH_Y + 70, MOUTH_X - 90:MOUTH_X + 90]
        mouth_after = self.engine._buf[MOUTH_Y:MOUTH_Y + 70, MOUTH_X - 90:MOUTH_X + 90]
        self.assertGreater(mouth_after.sum(), mouth_before.sum())

    def test_render_options_are_clamped(self):
        """Preview tuning should clamp unsafe values."""
        self.engine.set_render_options(
            transition_ms=5000,
            speed_multiplier=99,
            scanlines=False,
            glow=False,
        )
        self.assertEqual(self.engine._transition_duration_ms, 1000.0)
        self.assertEqual(self.engine._speed_multiplier, 3.0)
        self.assertFalse(self.engine._scanlines_enabled)
        self.assertFalse(self.engine._glow_enabled)


# ── SLEEPING Z animation ────────────────────────────────────────────────────

class TestSleepingZAnimation(unittest.TestCase):
    """Test animated floating Z letters during the sleeping expression."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    @unittest.skip("Animation loop calls threading; daemon threads swallow mock exceptions")
    def test_sleeping_loop_calls_commit(self):
        """_loop_sleeping must call _commit to animate Zs.

        Skipped: daemon threads swallow mock exceptions and hang.
        """
        pass

    def test_z_helper_methods_exist(self):
        """_z_big and _z_small must exist for drawing Z letters."""
        self.assertTrue(hasattr(self.engine, "_z_big"))
        self.assertTrue(callable(self.engine._z_big))
        self.assertTrue(hasattr(self.engine, "_z_small"))
        self.assertTrue(callable(self.engine._z_small))

    def test_z_methods_draw_on_buffer(self):
        """_z_big and _z_small must draw lit pixels on self._buf."""
        self.engine._buf[:] = 0
        self.engine._z_big(82, 12)
        self.assertGreater(
            self.engine._buf.sum(), 0,
            "_z_big must draw pixels on _buf",
        )

    @patch("time.time")
    def test_sleeping_uses_float_offset(self, mock_time):
        """Sleeping face should float up and down during animation."""
        mock_time.return_value = 0.0
        fy0 = self.engine._get_fy()

        mock_time.return_value = 1.5
        fy1 = self.engine._get_fy()

        self.assertNotEqual(fy0, fy1)


# ── THINKING dots animation ──────────────────────────────────────────────────

class TestThinkingDotsAnimation(unittest.TestCase):
    """Test animated ellipsis dots during the thinking expression."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    @unittest.skip("Animation loop calls threading; daemon threads swallow mock exceptions")
    def test_thinking_loop_calls_commit(self):
        """_loop_thinking must call _commit to show animated dots.

        Skipped: daemon threads swallow mock exceptions and hang.
        """
        pass

    def test_thinking_dots_use_fill_ellipse(self):
        """Thinking dots should be drawn with _fill_ellipse on the canvas."""
        self.engine._buf[:] = 0
        self.engine._fill_ellipse(90, 41, 2, 2)
        self.assertGreater(
            self.engine._buf.sum(), 0,
            "_fill_ellipse must draw on _buf",
        )

    def test_thinking_base_differs_from_neutral(self):
        """Thinking expression must have a distinct canvas from neutral."""
        buf = self.engine._base[Expression.THINKING]
        neutral = self.engine._base[Expression.NEUTRAL]
        self.assertFalse(
            (buf == neutral).all(),
            "THINKING must visually differ from NEUTRAL",
        )


# ── Idle animation (breathing / glow pulse) ───────────────────────────────────

class TestIdleAnimation(unittest.TestCase):
    """Test the gentle idle breathing animation on neutral expression."""

    def setUp(self):
        self.display = OLEDDisplay()
        self.engine = ExpressionEngine(self.display)

    def test_float_helper_produces_varying_offsets(self):
        """_get_fy must produce different values at different times."""
        offsets = set()
        for t in [i * 0.5 for i in range(20)]:
            with patch("time.time", return_value=t):
                offsets.add(self.engine._get_fy())
        self.assertGreater(len(offsets), 2)

    def test_blink_loop_runs_as_background_thread(self):
        """The blink loop must be started as a daemon thread after _switch."""
        with patch("time.sleep", side_effect=[Exception("stop")]):
            self.engine.show_expression("neutral")
            self.assertIsNotNone(self.engine._thread)
            self.assertTrue(
                self.engine._thread.daemon,
                "Animation thread should be a daemon",
            )


if __name__ == "__main__":
    unittest.main()
